# -*- coding: utf-8 -*-
from notion_client import Client
from config import NOTION_TOKEN, NOTION_DATABASE_ID
from datetime import datetime
import time
import pytz
import logging
from netease_api import get_playlist_tracks, get_user_playlists

# 在文件开头设置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 修改日志配置
logging.basicConfig(level=logging.ERROR, format='%(message)s')
logger = logging.getLogger(__name__)

notion = Client(auth=NOTION_TOKEN)

# 设置中国时区
china_tz = pytz.timezone('Asia/Shanghai')

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
def get_notion_records():
    results = notion.databases.query(database_id=NOTION_DATABASE_ID).get('results', [])
    records = {}
    for record in results:
        properties = record['properties']
        track_id = properties.get('歌曲ID', {}).get('rich_text', [{}])[0].get('text', {}).get('content')
        playlist_id = properties.get('歌单ID', {}).get('rich_text', [{}])[0].get('text', {}).get('content')
        if track_id and playlist_id:
            records[(str(track_id), str(playlist_id))] = record
    logger.info(f"从 Notion 数据库中检索到 {len(records)} 条记录")
    return records

@retry_on_failure
def sync_track_to_notion(track, playlist_id, playlist_name, status, index, total, action):
    existing_records = get_notion_records()
    track_id = str(track['id'])
    
    logger.info(f"同步歌曲 {track_id} 到 Notion。操作: {action}")
    
    database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    title_property = next(prop for prop, config in database['properties'].items() if config['type'] == 'title')
    
    cover_url = track.get('al', {}).get('picUrl', '')
    
    current_time = datetime.now(china_tz)
    publish_time = datetime.fromtimestamp(track['publishTime']/1000, china_tz) if 'publishTime' in track else None

    properties = {
        title_property: {"title": [{"text": {"content": track.get('name', "未知歌曲")}}]},
        "歌名": {"rich_text": [{"text": {"content": track.get('name', "未知歌曲")}}]},
        "歌单": {"rich_text": [{"text": {"content": playlist_name}}]},
        "封面": {"files": [{"name": "封面图片", "external": {"url": cover_url}}] if cover_url else []},
        "专辑": {"rich_text": [{"text": {"content": track.get('al', {}).get('name', "未知专辑")}}]},
        "发行日期": {"date": {"start": publish_time.isoformat() if publish_time else None}},
        "音乐链接": {"url": f"https://music.163.com/#/song?id={track['id']}"},
        "状态": {"select": {"name": status}},
        "最后同步日期": {"date": {"start": current_time.isoformat()}},
        "歌单ID": {"rich_text": [{"text": {"content": str(playlist_id)}}]},
        "歌曲ID": {"rich_text": [{"text": {"content": str(track_id)}}]}
    }
    
    existing_record = existing_records.get((str(track_id), str(playlist_id)))

    if existing_record:
        logger.info(f"更新现有记录，歌曲 {track_id}")
        notion.pages.update(
            page_id=existing_record['id'],
            properties=properties
        )
    else:
        logger.info(f"创建新记录，歌曲 {track_id}")
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )

    return f"[{index}/{total}] {action}歌曲: {track.get('name', '未知歌曲')} - ID: {track_id}, 状态: {status}, fee: {track.get('fee', 'N/A')}"

def get_status_color(status):
    status_colors = {
        '可用': 'green',
        'VIP': 'purple',
        '无版权': 'yellow',
        '已下架': 'red',
        '未知': 'gray'
    }
    return status_colors.get(status, 'gray')

@retry_on_failure
def mark_track_as_removed(track_id, playlist_id, playlist_name):
    existing_records = get_notion_records()
    if track_id in existing_records:
        record = existing_records[track_id]
        if record['properties']['歌单']['rich_text'][0]['text']['content'] == playlist_name:
            current_time = datetime.now(china_tz)
            notion.pages.update(
                page_id=record['id'],
                properties={
                    "状态": {"select": {"name": "已下架", "color": "red"}},
                    "最后同步日期": {"date": {"start": current_time.isoformat()}},
                }
            )
            return f"标记歌曲为已下架: ID {track_id}"
        else:
            return f"歌曲 ID {track_id} 不属于当前同步的歌单，跳过标记为已下架"
    else:
        return f"无法找到要标记为已下架的歌曲: ID {track_id}"

@retry_on_failure
def mark_track_as_removed_from_playlist(track_id, playlist_id, playlist_name):
    existing_records = get_notion_records()
    if track_id in existing_records:
        record = existing_records[track_id]
        if record['properties']['歌单']['rich_text'][0]['text']['content'] == playlist_name:
            current_time = datetime.now(china_tz)
            notion.pages.update(
                page_id=record['id'],
                properties={
                    "状态": {"select": {"name": "已取消收藏"}},
                    "最后同步日期": {"date": {"start": current_time.isoformat()}},
                }
            )
            return f"标记歌曲为已取消收藏: ID {track_id}"
        else:
            return f"歌曲 ID {track_id} 不属于当前同步的歌单，跳过处理"
    else:
        return f"无法找到要处理的歌曲: ID {track_id}"

@retry_on_failure
def mark_track_as_unavailable(track_id):
    existing_records = get_notion_records()
    if track_id in existing_records:
        record = existing_records[track_id]
        current_time = datetime.now(china_tz)
        notion.pages.update(
            page_id=record['id'],
            properties={
                "状态": {"select": {"name": "已下架"}},
                "最后同步日期": {"date": {"start": current_time.isoformat()}},
            }
        )
        return f"标记歌曲为已下架: ID {track_id}"
    else:
        return f"无法找到要标记为已下架的歌曲: ID {track_id}"

@retry_on_failure
def verify_notion_database_structure():
    try:
        logging.info("开始验证 Notion 数据库结构...")
        database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
        logging.info(f"成功检索到数据库。数据库 ID: {NOTION_DATABASE_ID}")
        existing_properties = database['properties']
        
        # 检查是否已存在 title 属性
        title_property = next((prop for prop, config in existing_properties.items() if config['type'] == 'title'), None)
        
        if not title_property:
            logging.error("错误：数据库中未到标题属性。请手动添加一个标题属性。")
            return False

        logging.info(f"使用现有的标题属性：{title_property}")

        required_properties = {
            '歌名': {'rich_text': {}},
            '歌单': {'rich_text': {}},  # 修改这里
            '封面': {'files': {}},
            '专辑': {'rich_text': {}},
            '发行日期': {'date': {}},
            '音乐链接': {'url': {}},
            '状态': {
                'select': {
                    'options': [
                        {'name': '可用', 'color': 'green'},
                        {'name': 'VIP', 'color': 'purple'},
                        {'name': '无版权', 'color': 'yellow'},
                        {'name': '已下架', 'color': 'red'},
                        {'name': '未知', 'color': 'gray'}
                    ]
                }
            },
            '最后同步日期': {'date': {}},
            '歌单ID': {'rich_text': {}},
            '歌曲ID': {'rich_text': {}}
        }

        properties_to_update = {}
        for prop_name, prop_config in required_properties.items():
            if prop_name not in existing_properties:
                logging.info(f"属性 '{prop_name}' 缺失。正在添加。")
                properties_to_update[prop_name] = prop_config
            elif existing_properties[prop_name]['type'] != list(prop_config.keys())[0]:
                logging.info(f"属性 '{prop_name}' 类型不正确。正在更新。")
                properties_to_update[prop_name] = prop_config

        if properties_to_update:
            logging.info("正在更新数据库属性...")
            notion.databases.update(
                database_id=NOTION_DATABASE_ID,
                properties=properties_to_update
            )
            logging.info("数据库属性更新成功。")
        else:
            logging.info("所有必需的属性已经存在于数据库中，并且类型正确。")

        logging.info("Notion 数据库结构验证和更新成功完成。")
        return True
    except Exception as e:
        logging.error(f"验证或更新 Notion 数据库结构时出错：{str(e)}")
        return False

@retry_on_failure
def get_notion_tracks():
    results = notion.databases.query(database_id=NOTION_DATABASE_ID).get('results', [])
    tracks = []
    
    # 获取数据库结构，找到标题属性
    database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    title_property = next((prop for prop, config in database['properties'].items() if config['type'] == 'title'), None)
    
    if not title_property:
        logging.error("错误：数据库中未找到标题属性。")
        return []

    for index, record in enumerate(results):
        properties = record['properties']
        try:
            # 检查记录是否为空
            if not any(properties.values()):
                continue

            track = {
                '歌手': properties.get(title_property, {}).get('title', [{}])[0].get('text', {}).get('content', '未知歌手'),
                '歌名': properties.get('歌名', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '未知歌曲'),
                '专辑': properties.get('专辑', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '未知专辑'),
                '音乐链接': properties.get('音乐链接', {}).get('url', ''),
                '状态': properties.get('状态', {}).get('select', {}).get('name', '未知'),
                '最后同步日期': properties.get('最后同步日期', {}).get('date', {}).get('start', ''),
                '歌单': properties.get('歌单', {}).get('rich_text', [{}])[0].get('text', {}).get('content', ''),
                '歌单ID': properties.get('歌单ID', {}).get('rich_text', [{}])[0].get('text', {}).get('content', ''),
                '歌曲ID': properties.get('歌曲ID', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '')
            }
            tracks.append(track)
        except Exception as e:
            logging.error(f"处理记录 {index + 1} 时出错: {str(e)}")
    
    logging.info(f"从 Notion 数据库中检索到 {len(tracks)} 条记录")
    return tracks

@retry_on_failure
def create_notion_playlist(playlist_info):
    properties = {
        "名称": {"title": [{"text": {"content": playlist_info['name']}}]},
        "歌单ID": {"rich_text": [{"text": {"content": str(playlist_info['id'])}}]},
        "创建者": {"rich_text": [{"text": {"content": playlist_info['creator']['nickname']}}]},
        "描述": {"rich_text": [{"text": {"content": playlist_info.get('description', '')}}]},
        "封面": {"files": [{"name": "封面图片", "external": {"url": playlist_info['coverImgUrl']}}]},
    }
    
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=properties
    )
    logger.info(f"在 Notion 中创建了新歌单: {playlist_info['name']}")

def main():
    verify_notion_database_structure()
    existing_records = get_notion_records()
    
    playlists = get_user_playlists()
    
    for playlist in playlists:
        playlist_id = playlist['id']
        playlist_name = playlist['name']
        tracks = get_playlist_tracks(playlist_id)
        
        for index, track in enumerate(tracks, 1):
            track_id = str(track['id'])
            status = "可用"  # 这里可以根据实际情况设置状态
            action = "更新" if track_id in existing_records else "新增"
            
            sync_track_to_notion(track, playlist_id, playlist_name, status, index, len(tracks), action)
        
        logger.info(f"Finished syncing playlist {playlist['name']} (ID: {playlist_id})")

if __name__ == "__main__":
    main()