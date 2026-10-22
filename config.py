import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    CHANNEL_ID = os.getenv("CHANNEL_ID", "")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    PER_PAGE = 60  # ← 直接写死，优先用这个

config = Config()