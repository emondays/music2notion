import requests
import time
import json
from config import NETEASE_COOKIE, NETEASE_USER_ID
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    """
    获取用户的所有歌单
    
    返回:
    list: 包含用户所有歌单信息的列表
    """
    url = f"{BASE_URL}/user/playlist?uid={NETEASE_USER_ID}&limit=1000&offset=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if 'playlist' in data:
            # 只返回用户创建的歌单，不包括收藏的歌单
            return [playlist for playlist in data['playlist'] if str(playlist['userId']) == NETEASE_USER_ID]
        else:
            print(f"意外的响应结构: {data}")
            raise Exception("获取用户播放列表失败。意外的响应结构。")
    raise Exception(f"获取用户播放列表失败。状态码: {response.status_code}")

def get_playlist_ids():
    """
    获取用户的所有歌单ID
    
    返回:
    list: 包含用户所有歌单ID的列表
    """
    playlists = get_user_playlists()
    return [str(playlist['id']) for playlist in playlists]

@retry_on_failure()
def check_track_availability(track_id):
    url = f"https://music.163.com/song?id={track_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://music.163.com/",
        "Cookie": NETEASE_COOKIE
    }
    logger.info(f"Checking availability for track ID: {track_id}")
    response = requests.get(url, headers=headers)
    
    logger.info(f"Response status code: {response.status_code}")
    logger.info(f"Response content length: {len(response.text)}")
    
    if response.status_code == 404:
        logger.info(f"Track {track_id} is not available (404 Not Found)")
        return False
    elif response.status_code == 200:
        if "很抱歉，你要查找的网页找不到" in response.text:
            logger.info(f"Track {track_id} is not available (Page content indicates not found)")
            return False
        else:
            logger.info(f"Track {track_id} is available")
            return True
    else:
        logger.error(f"Unexpected status code {response.status_code} for track ID {track_id}")
        return False

# 新增函数
def update_notion_database_structure(notion_client, database_id):
    """
    更新 Notion 数据库结构，隐藏 '歌曲ID' 和 '歌单ID' 列，并设置标题属性
    """
    properties = {
        "歌曲ID": {"name": "歌曲ID", "type": "number", "number": {"format": "number"}},
        "歌单ID": {"name": "歌单ID", "type": "number", "number": {"format": "number"}},
        "名称": {"name": "名称", "type": "title"}  # 添加标题属性
    }
    
    for prop_name, prop_config in properties.items():
        notion_client.databases.update(
            database_id=database_id,
            properties={
                prop_name: {
                    "type": prop_config["type"],
                    prop_config["type"]: prop_config.get(prop_config["type"], {}),
                    "name": prop_name,
                    "hidden": prop_name in ["歌曲ID", "歌单ID"]
                }
            }
        )
    
    logger.info("已更新 Notion 数据库结构，隐藏了 '歌曲ID' 和 '歌单ID' 列，并设置了标题属性")

# 在主函数或初始化过程中调用此函数
# update_notion_database_structure(notion_client, NOTION_DATABASE_ID)

def get_notion_database_structure(notion_client, database_id):
    """
    获取 Notion 数据库结构
    """
    database = notion_client.databases.retrieve(database_id=database_id)
    return database.properties

def sync_playlist_to_notion(notion_client, database_id, playlist_tracks, playlist_info):
    """
    同步播放列表到 Notion 数据库
    """
    database_structure = get_notion_database_structure(notion_client, database_id)
    title_property = next((prop for prop, details in database_structure.items() if details["type"] == "title"), None)
    
    if not title_property:
        raise ValueError("Notion 数据库中未找到标题属性")

    # ... 其余同步逻辑 ...

    for track in playlist_tracks:
        # 使用 title_property 作为标题属性
        new_page = {
            "parent": {"database_id": database_id},
            "properties": {
                title_property: {"title": [{"text": {"content": track["name"]}}]},
                "歌名": {"rich_text": [{"text": {"content": track["name"]}}]},
                "播放列表": {"rich_text": [{"text": {"content": playlist_info["name"]}}]},
                # ... 其他属性 ...
            }
        }
        notion_client.pages.create(**new_page)

    # ... 其余同步逻辑 ...

# 在主函数中调用 sync_playlist_to_notion