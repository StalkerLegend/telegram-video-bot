import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO)

# ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT      = int(os.getenv("PORT", "8000"))
DOWNLOADS = "downloads"

if not BOT_TOKEN:
    logging.error("❌ Не задан BOT_TOKEN")
    exit(1)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()
os.makedirs(DOWNLOADS, exist_ok=True)

YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "logger": logging.getLogger("yt-dlp"),
}

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Я бот-скачалка видео (YouTube, TikTok, Insta, Pinterest).\n"
        "Отправь ссылку. Если видео ≤50 МБ — пришлю файл, иначе — ссылку."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Отправь, пожалуйста, ссылку на видео.")

    status = await message.reply("⏳ Скачиваю… подожди минутку")
    filename = None

    try:
        # heavy work in thread
        def yt_download():
            with YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await asyncio.to_thread(yt_download)
        size = os.path.getsize(filename)
        logging.info(f"Downloaded {filename}, size={size}")

        if size <= 50 * 1024 * 1024:
            await message.reply_video(FSInputFile(filename))
        else:
            public = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Скачано ({size//1024**2} МБ), слишком большой файл.\n"
                f"Скачать тут:\n{public}"
            )
    except Exception as e:
        logging.exception("Ошибка при скачивании")
        await message.reply(f"❌ Ошибка:\n`{e}`", parse_mode="Markdown")
    finally:
        await status.delete()
        if filename and os.path.exists(filename):
            os.remove(filename)

async def start_polling():
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    # 1) aiohttp для Render
    app = web.Application()
    # простой health-check
    async def ping(request): return web.Response(text="OK")
    app.add_routes([web.get("/", ping)])
    # отдача статики
    app.router.add_static("/", DOWNLOADS, show_index=True)

    # 2) Запускаем polling и HTTP-сервер параллельно
    loop = asyncio.get_event_loop()
    loop.create_task(start_polling())
    logging.info(f"🚀 Запуск HTTP на порту {PORT} и polling")
    web.run_app(app, host="0.0.0.0", port=PORT)
