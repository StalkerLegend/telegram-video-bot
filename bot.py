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

# Переменные окружения
BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT        = int(os.getenv("PORT", 8443))
DOWNLOADS   = "downloads"

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Задайте BOT_TOKEN и WEBHOOK_URL!")
    exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
os.makedirs(DOWNLOADS, exist_ok=True)

# Настройки yt-dlp без вывода прогресса
YDL_OPTS = {
    "format": "bestvideo+ bestaudio/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "logger": logging.getLogger("yt-dlp"),
}

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Я бот для скачивания видео из YouTube, TikTok, Instagram и Pinterest.\n"
        "Отправь ссылку, и я пришлю готовый файл (до 50 МБ) или ссылку на скачивание."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Пожалуйста, отправь корректную ссылку!")

    status_msg = await message.reply("⏳ Скачиваю видео… Это может занять до минуты.")

    filename = None
    try:
        # Вынесем тяжёлую работу в отдельный поток
        def download():
            with YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await asyncio.to_thread(download)
        size = os.path.getsize(filename)
        logging.info(f"Downloaded {filename}, size={size} bytes")

        if size <= 50 * 1024 * 1024:
            video = FSInputFile(filename)
            await message.reply_video(video)
        else:
            base = WEBHOOK_URL.rsplit("/webhook", 1)[0]
            public = f"{base}/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Видео ({size//1024**2} МБ) скачано, но Telegram не примет такой объём.\n"
                f"Скачать можно здесь:\n{public}"
            )

    except Exception as e:
        logging.exception("Ошибка при скачивании/отправке видео")
        await message.reply(f"❌ Не удалось скачать видео:\n`{e}`", parse_mode="Markdown")
    finally:
        # удаляем локальный файл
        if filename and os.path.exists(filename):
            try: os.remove(filename)
            except: pass
        # удаляем «Скачиваю…» сообщение
        await status_msg.delete()

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
