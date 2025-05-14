import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from yt_dlp import YoutubeDL

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # https://<your-service>.onrender.com/webhook
PORT        = int(os.getenv("PORT", 8443))  # Telegram поддерживает 443,80,88,8443
DOWNLOADS   = "downloads"

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Задайте в ENV BOT_TOKEN и WEBHOOK_URL!")
    exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# Папка для скачанных видео
os.makedirs(DOWNLOADS, exist_ok=True)

# Опции yt-dlp
YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
}

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Привет! Я скачиваю видео из YouTube, TikTok, Instagram и Pinterest.\n"
        "Просто отправь ссылку.\n"
        "⚠️ Максимум 50 МБ для отправки в чат — если больше, дам прямую ссылку."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Пожалуйста, отправь корректную ссылку.")

    await message.reply("⏳ Скачиваю…")
    filename = None

    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        size = os.path.getsize(filename)
        if size <= 50 * 1024 * 1024:
            video = InputFile(path_or_bytesio=filename)
            await message.reply_video(video)
        else:
            public_url = WEBHOOK_URL.rsplit("/webhook", 1)[0] + f"/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Видео скачано ({size//
