import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

# 🫀 Загружаем .env
load_dotenv(dotenv_path='secrets/.env')

TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID"))

# ⚙️ aiogram 3.7+ поддерживает только default=
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher()
