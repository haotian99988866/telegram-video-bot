import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    CHANNEL_ID = os.getenv("CHANNEL_ID", "")
    ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
    PER_PAGE = int(os.getenv("PER_PAGE", 6))

config = Config()