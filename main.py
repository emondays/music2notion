import time
import json
from config import get_playlist_ids
from netease_api import get_playlist_info, get_playlist_tracks
from notion_api import sync_track_to_notion, verify_notion_database_structure, get_notion_tracks, mark_track_as_removed

PROGRESS_FILE = 'sync_progress.json'

def load_progress():
    try:
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_progress(playlist_id, index):
    progress = load_progress()
    progress[playlist_id] = index
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def compare_tracks(netease_tracks, notion_tracks, playlist_name):
    netease_track_dict = {str(track['id']): track for track in netease_tracks}
    notion_track_dict = {
        track['音乐链接'].split('=')[-1]: track 
        for track in notion_tracks 
        if track['播放列表'] == playlist_name
    }

    to_add = []
    to_update = []
    to_remove = []

    for track_id, track in netease_track_dict.items():
        if track_id not in notion_track_dict:
            to_add.append(track)
        elif needs_update(track, notion_track_dict[track_id]):
            to_update.append(track)

    for track_id in notion_track_dict:
        if track_id not in netease_track_dict:
            to_remove.append(track_id)

    return to_add, to_update, to_remove

def needs_update(netease_track, notion_track):
    # 比较关键字段，如果有不同则需要更新
    return (
        netease_track['name'] != notion_track['歌名'] or
        netease_track['ar'][0]['name'] != notion_track['歌手'] or
        netease_track['al']['name'] != notion_track['专辑'] or
        notion_track['状态'] != '可用'
    )

def sync_playlist(playlist_id):
    playlist_info = get_playlist_info(playlist_id)
    playlist_name = playlist_info['name']
    print(f"\n正在同步播放列表: {playlist_name}")
    print(f"播放列表总曲目数: {playlist_info['trackCount']}")

    netease_tracks = get_playlist_tracks(playlist_id)
    notion_tracks = get_notion_tracks()
    print(f"从 Notion 获取到的歌曲数量: {len(notion_tracks)}")

    to_add, to_update, to_remove = compare_tracks(netease_tracks, notion_tracks, playlist_name)

    print(f"需要添加的歌曲数: {len(to_add)}")
    print(f"需要更新的歌曲数: {len(to_update)}")
    print(f"需要标记为已下架的歌曲数: {len(to_remove)}")

    if not to_add and not to_update and not to_remove:
        print(f"播放列表 '{playlist_name}' 无需同步，跳过。")
        return

    print("\n开始同步歌曲到 Notion...")
    for track in to_add:
        result = sync_track_to_notion(track, playlist_name, "可用")
        print(result)

    for track in to_update:
        result = sync_track_to_notion(track, playlist_name, "可用")
        print(result)

    for track_id in to_remove:
        result = mark_track_as_removed(track_id, playlist_name)
        print(result)

    print(f"播放列表 '{playlist_name}' 同步完成")

def main():
    if not verify_notion_database_structure():
        print("Notion数据库结构验证失败，请检查并修复问题后重试。")
        return

    playlist_ids = get_playlist_ids()
    print(f"将要同步的播放列表数量: {len(playlist_ids)}")

    for playlist_id in playlist_ids:
        sync_playlist(playlist_id)

    print("\n所有播放列表同步完成")

if __name__ == "__main__":
    main()