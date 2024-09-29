import os
from dotenv import load_dotenv
import logging

# 设置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

NETEASE_COOKIE = os.getenv('NETEASE_COOKIE')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
NETEASE_USER_ID = os.getenv('NETEASE_USER_ID')

# 打印环境变量（不包括完整的 cookie）
logging.info(f"NETEASE_USER_ID: {NETEASE_USER_ID}")
logging.info(f"NOTION_TOKEN: {NOTION_TOKEN[:10]}..." if NOTION_TOKEN else "NOTION_TOKEN 未设置")
logging.info(f"NOTION_DATABASE_ID: {NOTION_DATABASE_ID}" if NOTION_DATABASE_ID else "NOTION_DATABASE_ID 未设置")
logging.info(f"NETEASE_COOKIE length: {len(NETEASE_COOKIE)}" if NETEASE_COOKIE else "NETEASE_COOKIE 未设置")

# 添加额外的检查
if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    raise ValueError("NOTION_TOKEN 或 NOTION_DATABASE_ID 未正确设置。请检查您的 .env 文件。")

if len(NOTION_DATABASE_ID) != 36:
    raise ValueError(f"NOTION_DATABASE_ID 长度不正确。应为 36 个字符，当前长度为 {len(NOTION_DATABASE_ID)}。")

logging.info("配置加载完成，所有必要的环境变量都已设置。")