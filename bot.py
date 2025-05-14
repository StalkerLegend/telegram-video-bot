import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO)

BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT        = int(os.getenv("PORT", 8443))
DOWNLOADS   = "downloads"

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Задайте в ENV BOT_TOKEN и WEBHOOK_URL!")
    exit(1)

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
os.makedirs(DOWNLOADS, exist_ok=True)

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
        "Просто отправь мне ссылку.\n"
        "⚠️ Максимум 50 МБ для отправки в чат — если файл больше, дам прямую ссылку."
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
            video = FSInputFile(filename)
            await message.reply_video(video)
        else:
            base_url = WEBHOOK_URL.rsplit("/webhook", 1)[0]
            public_url = f"{base_url}/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Видео скачано ({size // 1024**2} МБ), но оно слишком большое для Telegram.\n"
                f"Скачайте его здесь:\n{public_url}"
            )
    except Exception as e:
        logging.exception("Ошибка при загрузке/отправке видео")
        await message.reply(f"❌ Произошла ошибка:\n{e}")
    finally:
        if filename and os.path.exists(filename):
            try: os.remove(filename)
            except: pass

async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

if __name__ == "__main__":
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    app.on_startup.append(lambda _: asyncio.create_task(on_startup()))
    app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown()))
    app.router.add_static("/", DOWNLOADS, show_index=True)

    logging.info(f"🚀 Запуск на порту {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
