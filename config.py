import os
from dotenv import load_dotenv

load_dotenv()

NETEASE_COOKIE = os.getenv('NETEASE_COOKIE')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
NETEASE_USER_ID = os.getenv('NETEASE_USER_ID')

# 打印环境变量（不包括完整的 cookie）
print(f"NETEASE_USER_ID: {NETEASE_USER_ID}")
print(f"NOTION_TOKEN: {NOTION_TOKEN[:10]}...")  # 只打印前10个字符
print(f"NOTION_DATABASE_ID: {NOTION_DATABASE_ID}")
print(f"NETEASE_COOKIE length: {len(NETEASE_COOKIE)}")