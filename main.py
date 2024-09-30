import time
import json
from netease_api import get_playlist_info, get_playlist_tracks, get_playlist_ids, check_track_availability
from notion_api import sync_track_to_notion, verify_notion_database_structure, get_notion_tracks, mark_track_as_removed_from_playlist, mark_track_as_unavailable, create_notion_playlist

PROGRESS_FILE = 'sync_progress.json'

def load_progress():
    try:
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)

def compare_tracks(netease_tracks, notion_tracks, playlist_id, playlist_name):
    netease_track_dict = {str(track['id']): track for track in netease_tracks}
    notion_track_dict = {
        str(track['歌曲ID']): track 
        for track in notion_tracks 
        if str(track['歌单ID']) == str(playlist_id) and track['歌单'] == playlist_name
    }

    print(f"网易云歌单 {playlist_name} (ID: {playlist_id}) 歌曲数: {len(netease_track_dict)}")
    print(f"Notion歌单 {playlist_name} (ID: {playlist_id}) 歌曲数: {len(notion_track_dict)}")

    to_add = []
    to_update = []
    to_remove = []

    for track_id, track in netease_track_dict.items():
        if track_id not in notion_track_dict:
            print(f"需要新增: {track['name']} (ID: {track_id})")
            to_add.append(track)
        elif needs_update(track, notion_track_dict[track_id]):
            print(f"需要更新: {track['name']} (ID: {track_id})")
            print(f"网易云状态: {get_status_from_fee(track.get('fee', 0))}, Notion状态: {notion_track_dict[track_id]['状态']}")
            to_update.append(track)

    for track_id, notion_track in notion_track_dict.items():
        if track_id not in netease_track_dict:
            print(f"需要处理: {notion_track['歌名']} (ID: {track_id})")
            to_remove.append(notion_track)

    return to_add, to_update, to_remove

def needs_update(netease_track, notion_track):
    netease_status = get_status_from_fee(netease_track.get('fee', 0))
    notion_status = notion_track['状态']
    if netease_status != notion_status:
        print(f"状态变化: {notion_status} -> {netease_status}")
        return True
    return False

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
    print(f"\n同步歌单 {playlist_index}/{total_playlists}: {playlist_name} (ID: {playlist_id})")
    print(f"曲目数: {playlist_info['trackCount']}")

    netease_tracks = get_playlist_tracks(playlist_id)
    notion_tracks = get_notion_tracks()

    # 检查 Notion 中是否存在该歌单
    notion_playlist = next((p for p in notion_tracks if str(p['歌单ID']) == str(playlist_id)), None)
    
    if not notion_playlist:
        print(f"Notion 中不存在歌单 {playlist_name}，正在创建...")
        create_notion_playlist(playlist_info)
        to_add = netease_tracks
        to_update = []
        to_remove = []
    else:
        to_add, to_update, to_remove = compare_tracks(netease_tracks, notion_tracks, playlist_id, playlist_name)

    print(f"新增: {len(to_add)}, 更新: {len(to_update)}, 处理: {len(to_remove)}")

    if not to_add and not to_update and not to_remove:
        print(f"'{playlist_name}' 无需同步")
        return

    for index, track in enumerate(to_add, 1):
        status = get_status_from_fee(track.get('fee', 0))
        result = sync_track_to_notion(track, playlist_id, playlist_name, status, index, len(to_add), "新增")
        print(result)

    for index, track in enumerate(to_update, 1):
        status = get_status_from_fee(track.get('fee', 0))
        result = sync_track_to_notion(track, playlist_id, playlist_name, status, index, len(to_update), "更新")
        print(result)

    for index, notion_track in enumerate(to_remove, 1):
        track_id = notion_track['歌曲ID']
        availability = check_track_availability(track_id)
        print(f"歌曲 ID {track_id} 在网易云曲库中的可用性: {availability}")
        if availability:
            result = mark_track_as_removed_from_playlist(track_id, playlist_id, playlist_name)
            print(result)
        else:
            result = mark_track_as_unavailable(track_id, playlist_id)
            print(result)

    print(f"'{playlist_name}' 同步完成")

# 在 main 函数中，简化输出
def main():
    if not verify_notion_database_structure():
        print("Notion数据库结构验证失败，请检查并修复问题后重试。")
        return

    playlist_ids = get_playlist_ids()
    print(f"用户歌单数量: {len(playlist_ids)}")

    progress = load_progress()
    start_index = max(progress.values()) if progress else 0

    for index, playlist_id in enumerate(playlist_ids[start_index:], start_index + 1):
        print(f"开始同步歌单 {index}/{len(playlist_ids)}: ID {playlist_id}")
        sync_playlist(playlist_id, index, len(playlist_ids))
        progress[playlist_id] = index
        save_progress(progress)
        print(f"歌单 {index}/{len(playlist_ids)}: ID {playlist_id} 同步完成")

    print("\n所有播放列表同步完成")
    # 同步完成后清除进度文件
    save_progress({})

import logging
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    main()