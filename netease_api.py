import requests
import time
from config import NETEASE_COOKIE, NETEASE_USER_ID

def retry_on_failure(func):
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"Error occurred: {str(e)}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise
    return wrapper

@retry_on_failure
def get_playlist_details(playlist_id):
    url = f"https://music.163.com/api/v6/playlist/detail?id={playlist_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    response = requests.get(url, headers=headers)
    print(f"Playlist details response: {response.text[:200]}...")  # 打印响应的前200个字符
    if response.status_code == 200:
        data = response.json()
        if 'playlist' in data:
            return data['playlist']
    raise Exception(f"Failed to fetch playlist {playlist_id}. Status code: {response.status_code}")

@retry_on_failure
def get_user_playlists():
    url = f"https://music.163.com/api/user/playlist?uid={NETEASE_USER_ID}&limit=30&offset=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    response = requests.get(url, headers=headers)
    print(f"User playlists response: {response.text[:200]}...")  # 打印响应的前200个字符
    if response.status_code == 200:
        data = response.json()
        if 'playlist' in data:
            return data['playlist']
        else:
            print(f"Unexpected response structure: {data}")
            raise Exception("Failed to fetch user playlists. Unexpected response structure.")
    raise Exception(f"Failed to fetch user playlists. Status code: {response.status_code}")