from notion_client import Client
from config import NOTION_TOKEN, NOTION_DATABASE_ID
from datetime import datetime
import time

notion = Client(auth=NOTION_TOKEN)

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
    return {record['properties']['音乐链接']['url'].split('=')[-1]: record for record in results}

@retry_on_failure
def sync_track_to_notion(track, playlist_name):
    existing_records = get_notion_records()
    track_id = str(track['id'])
    
    database = notion.databases.retrieve(database_id=NOTION_DATABASE_ID)
    title_property = next(prop for prop, config in database['properties'].items() if config['type'] == 'title')
    
    if track_id in existing_records:
        notion.pages.update(
            page_id=existing_records[track_id]['id'],
            properties={
                title_property: {"title": [{"text": {"content": track['ar'][0]['name']}}]},
                "状态": {"select": {"name": "可用" if track.get('fee') != 1 else "无版权"}},
                "最后同步日期": {"date": {"start": datetime.now().isoformat()}},
            }
        )
    else:
        properties = {
            title_property: {"title": [{"text": {"content": track['ar'][0]['name']}}]},
            "歌名": {"rich_text": [{"text": {"content": track['name']}}]},
            "封面": {"url": track['al']['picUrl']},
            "专辑": {"rich_text": [{"text": {"content": track['al']['name']}}]},
            "发行日期": {"date": {"start": datetime.fromtimestamp(track['publishTime']/1000).isoformat() if 'publishTime' in track else None}},
            "音乐链接": {"url": f"https://music.163.com/#/song?id={track['id']}"},
            "播放列表": {"rich_text": [{"text": {"content": playlist_name}}]},
            "状态": {"select": {"name": "可用" if track.get('fee') != 1 else "无版权"}},
            "最后同步日期": {"date": {"start": datetime.now().isoformat()}},
        }
        notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )

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
            '封面': {'url': {}},
            '专辑': {'rich_text': {}},
            '发行日期': {'date': {}},
            '音乐链接': {'url': {}},
            '播放列表': {'rich_text': {}},
            '状态': {
                'select': {
                    'options': [
                        {'name': '可用', 'color': 'green'},
                        {'name': '无版权', 'color': 'yellow'},
                        {'name': '已消失', 'color': 'red'}
                    ]
                }
            },
            '最后同步日期': {'date': {}}
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