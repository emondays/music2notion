from notion_client import Client
from config import NOTION_TOKEN, NOTION_DATABASE_ID
from datetime import datetime
import time
import pytz
import logging

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
    for index, record in enumerate(results):
        try:
            properties = record['properties']
            music_link = properties.get('音乐链接', {}).get('url')
            if music_link:
                track_id = music_link.split('=')[-1]
                records[track_id] = record
            else:
                logger.debug(f"Record {index} has no music link: {properties}")
        except Exception as e:
            logger.error(f"Error processing record {index}: {str(e)}")
    
    logger.debug(f"Total records processed: {len(records)}")
    return records

@retry_on_failure
def sync_track_to_notion(track, playlist_id, status, index, total, action):
    existing_records = get_notion_records()
    track_id = str(track['id'])
    
    database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    title_property = next(prop for prop, config in database['properties'].items() if config['type'] == 'title')
    
    cover_url = track.get('al', {}).get('picUrl', '')
    
    # 使用中国时区
    current_time = datetime.now(china_tz)
    publish_time = datetime.fromtimestamp(track['publishTime']/1000, china_tz) if 'publishTime' in track else None

    properties = {
        title_property: {"title": [{"text": {"content": track['ar'][0]['name'] if 'ar' in track and track['ar'] else "未知歌手"}}]},
        "歌名": {"rich_text": [{"text": {"content": track.get('name', "未知歌曲")}}]},
        "封面": {"files": [{"name": "封面图片", "external": {"url": cover_url}}] if cover_url else []},
        "专辑": {"rich_text": [{"text": {"content": track.get('al', {}).get('name', "未知专辑")}}]},
        "发行日期": {"date": {"start": publish_time.isoformat() if publish_time else None}},
        "音乐链接": {"url": f"https://music.163.com/#/song?id={track['id']}"},
        "播放列表": {"rich_text": [{"text": {"content": playlist_id}}]},
        "状态": {"select": {"name": status, "color": get_status_color(status)}},
        "最后同步日期": {"date": {"start": current_time.isoformat()}},
        "歌单ID": {"number": int(playlist_id)},
        "歌曲ID": {"number": int(track_id)}
    }
    
    if action == "更新" and track_id in existing_records:
        notion.pages.update(
            page_id=existing_records[track_id]['id'],
            properties=properties
        )
    else:
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
def mark_track_as_removed(track_id, playlist_id):
    existing_records = get_notion_records()
    if track_id in existing_records:
        record = existing_records[track_id]
        if record['properties']['播放列表']['rich_text'][0]['text']['content'] == playlist_id:
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
            return f"歌曲 ID {track_id} 不属于当前同步的播放列表，跳过标记为已下架"
    else:
        return f"无法找到要标记为已下架的歌曲: ID {track_id}"

@retry_on_failure
def verify_notion_database_structure():
    try:
        print("Verifying Notion database structure...")
        database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
        existing_properties = database['properties']
        
        # 检查是否已存在 title 属性
        title_property = next((prop for prop, config in existing_properties.items() if config['type'] == 'title'), None)
        
        if not title_property:
            print("Error: No title property found in the database.")
            print("Please add a title property manually in the Notion interface:")
            print("1. Open your Notion database")
            print("2. Click on the '+' button next to the existing columns")
            print("3. Choose 'Title' as the property type")
            print("4. Name it 'Title' or any name you prefer")
            print("5. Drag it to be the first column if it's not already")
            return False

        print(f"Existing title property found: {title_property}")

        required_properties = {
            '歌名': {'rich_text': {}},
            '封面': {'files': {}},
            '专辑': {'rich_text': {}},
            '发行日期': {'date': {}},
            '音乐链接': {'url': {}},
            '播放列表': {'rich_text': {}},
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
            '单ID': {'number': {}},
            '歌曲ID': {'number': {}}
        }

        properties_to_update = {}
        for prop_name, prop_config in required_properties.items():
            if prop_name not in existing_properties:
                print(f"Property '{prop_name}' is missing. Adding it.")
                properties_to_update[prop_name] = prop_config
            elif existing_properties[prop_name]['type'] != list(prop_config.keys())[0]:
                print(f"Property '{prop_name}' has incorrect type. Updating it.")
                properties_to_update[prop_name] = prop_config

        if properties_to_update:
            print("Updating database properties...")
            notion.databases.update(
                database_id=NOTION_DATABASE_ID,
                properties=properties_to_update
            )
            print("Database properties updated successfully.")
        else:
            print("All required properties already exist in the database with correct types.")

        print("Notion database structure verified and updated successfully.")
        return True
    except Exception as e:
        print(f"Error verifying or updating Notion database structure: {str(e)}")
        return False

@retry_on_failure
def get_notion_tracks():
    results = notion.databases.query(database_id=NOTION_DATABASE_ID).get('results', [])
    tracks = []
    for index, record in enumerate(results):
        properties = record['properties']
        try:
            track = {
                '歌手': properties.get(next(prop for prop, config in properties.items() if config['type'] == 'title'), {}).get('title', [{}])[0].get('text', {}).get('content', '未知歌手'),
                '歌名': properties.get('歌名', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '未知歌曲'),
                '专辑': properties.get('专辑', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '未知专辑'),
                '音乐链接': properties.get('音乐链接', {}).get('url', ''),
                '状态': properties.get('状态', {}).get('select', {}).get('name', '未知'),
                '最后同步日期': properties.get('最后同步日期', {}).get('date', {}).get('start', ''),
                '播放列表': properties.get('播放列表', {}).get('rich_text', [{}])[0].get('text', {}).get('content', ''),
                '歌单ID': properties.get('歌单ID', {}).get('number', 0),
                '歌曲ID': properties.get('歌曲ID', {}).get('number', 0)
            }
            tracks.append(track)
            print(f"Notion 记录 {index + 1}: 歌名 '{track['歌名']}', 歌单ID '{track['歌单ID']}', 歌曲ID '{track['歌曲ID']}'")
        except Exception as e:
            logger.error(f"Error processing record {index + 1}: {str(e)}")
    
    return tracks