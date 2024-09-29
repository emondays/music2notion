import time
import json
from netease_api import get_playlist_info, get_playlist_tracks, get_playlist_ids
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

def compare_tracks(netease_tracks, notion_tracks, playlist_id):
    netease_track_dict = {str(track['id']): track for track in netease_tracks}
    notion_track_dict = {
        str(track['歌曲ID']): track 
        for track in notion_tracks 
        if str(track['歌单ID']) == str(playlist_id)
    }

    print(f"网易云歌单 {playlist_id} 歌曲数: {len(netease_track_dict)}")
    print(f"Notion歌单 {playlist_id} 歌曲数: {len(notion_track_dict)}")

    to_add = []
    to_update = []
    to_remove = []

    for track_id, track in netease_track_dict.items():
        if track_id not in notion_track_dict:
            print(f"需要新增: {track['name']} (ID: {track_id})")
            to_add.append(track)
        elif needs_update(track, notion_track_dict[track_id]):
            print(f"需要更新: {track['name']} (ID: {track_id})")
            to_update.append(track)

    for track_id in notion_track_dict:
        if track_id not in netease_track_dict:
            print(f"需要删除: {notion_track_dict[track_id]['歌名']} (ID: {track_id})")
            to_remove.append(track_id)

    return to_add, to_update, to_remove

def needs_update(netease_track, notion_track):
    netease_status = get_status_from_fee(netease_track.get('fee', 0))
    notion_status = notion_track['状态']
    
    return (
        netease_status != notion_status or
        netease_track['name'] != notion_track['歌名'] or
        netease_track['ar'][0]['name'] != notion_track['歌手'] or
        netease_track['al']['name'] != notion_track['专辑']
    )

def get_status_from_fee(fee):
    if fee == 0:
        return '无版权'
    elif fee == 1:
        return 'VIP'
    elif fee == 8:
        return '可用'
    else:
        return '未知'

def sync_playlist(playlist_id, playlist_index, total_playlists):
    playlist_info = get_playlist_info(playlist_id)
    playlist_name = playlist_info['name']
    print(f"\n同步播放列表 {playlist_index}/{total_playlists}: {playlist_name} (ID: {playlist_id})")
    print(f"曲目数: {playlist_info['trackCount']}")

    netease_tracks = get_playlist_tracks(playlist_id)
    notion_tracks = get_notion_tracks()

    to_add, to_update, to_remove = compare_tracks(netease_tracks, notion_tracks, playlist_id)

    print(f"新增: {len(to_add)}, 更新: {len(to_update)}, 下架: {len(to_remove)}")

    if not to_add and not to_update and not to_remove:
        print(f"'{playlist_name}' 无需同步")
        return

    for index, track in enumerate(to_add, 1):
        status = get_status_from_fee(track.get('fee', 0))
        result = sync_track_to_notion(track, playlist_id, status, index, len(to_add), "新增")
        print(result)

    for index, track in enumerate(to_update, 1):
        status = get_status_from_fee(track.get('fee', 0))
        result = sync_track_to_notion(track, playlist_id, status, index, len(to_update), "更新")
        print(result)

    for index, track_id in enumerate(to_remove, 1):
        result = mark_track_as_removed(track_id, playlist_id)
        print(result)

    print(f"'{playlist_name}' 同步完成")

# 在 main 函数中，简化输出
def main():
    if not verify_notion_database_structure():
        print("Notion数据库结构验证失败，请检查并修复问题后重试。")
        return

    playlist_ids = get_playlist_ids()
    print(f"用户歌单数量: {len(playlist_ids)}")

    for index, playlist_id in enumerate(playlist_ids, 1):
        sync_playlist(playlist_id, index, len(playlist_ids))

    print("\n所有播放列表同步完成")

import logging
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    main()