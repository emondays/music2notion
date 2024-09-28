import time
from config import NOTION_DATABASE_ID
from netease_api import get_user_playlists, get_playlist_details
from notion_api import sync_track_to_notion, verify_notion_database_structure

def main():
    print("Starting sync process...")
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            if not verify_notion_database_structure():
                print("Failed to verify Notion database structure. Exiting.")
                return
            
            playlists = get_user_playlists()
            for playlist in playlists:
                print(f"Syncing playlist: {playlist['name']}")
                tracks = get_playlist_details(playlist['id'])['tracks']
                for track in tracks:
                    sync_track_to_notion(track, playlist['name'])
            
            print("Sync completed successfully")
            return  # 成功完成，退出函数
        except Exception as e:
            print(f"An error occurred (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Exiting.")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    main()