import requests
import time
import json
from config import NETEASE_COOKIE, NETEASE_USER_ID
from functools import wraps

BASE_URL = "https://music.163.com/api"

def retry_on_failure(max_retries=3, retry_delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"错误发生: {str(e)}。{retry_delay}秒后重试...")
                        time.sleep(retry_delay)
                    else:
                        raise
        return wrapper
    return decorator

@retry_on_failure()
def get_playlist_info(playlist_id):
    url = f"{BASE_URL}/v6/playlist/detail?id={playlist_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'playlist' in data:
            return data['playlist']
    raise Exception(f"获取播放列表 {playlist_id} 失败。状态码: {response.status_code}")

@retry_on_failure()
def get_playlist_tracks(playlist_id):
    all_tracks = []
    offset = 0
    limit = 1000  # 每次请求的最大数量
    
    while True:
        url = f"{BASE_URL}/v6/playlist/detail?id={playlist_id}&limit={limit}&offset={offset}&n={limit}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "https://music.163.com/",
            "Cookie": NETEASE_COOKIE
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data['code'] != 200:
            raise Exception(f"获取播放列表失败: {data.get('message', '未知错误')}")
        
        tracks = data['playlist']['tracks']
        all_tracks.extend(tracks)
        
        if len(tracks) < limit:
            break
        
        offset += limit
        time.sleep(1)  # 添加1秒延迟
    
    print(f"获取到的歌曲数量: {len(all_tracks)}")
    return all_tracks

@retry_on_failure()
def get_user_playlists():
    url = f"{BASE_URL}/user/playlist?uid={NETEASE_USER_ID}&limit=30&offset=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'playlist' in data:
            return [playlist for playlist in data['playlist'] if str(playlist['userId']) == NETEASE_USER_ID]
        else:
            print(f"意外的响应结构: {data}")
            raise Exception("获取用户播放列表失败。意外的响应结构。")
    raise Exception(f"获取用户播放列表失败。状态码: {response.status_code}")