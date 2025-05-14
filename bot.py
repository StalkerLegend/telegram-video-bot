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

# ——————————————————————————————————————————————
# 1) Получаем обязательные переменные окружения
BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # https://<your-service>.onrender.com/webhook
PORT        = int(os.getenv("PORT", "8000"))  # Render всегда задаёт PORT
DOWNLOADS   = "downloads"

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Не заданы BOT_TOKEN или WEBHOOK_URL в ENV")
    exit(1)

# ——————————————————————————————————————————————
# 2) Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# 3) Папка для скачивания
os.makedirs(DOWNLOADS, exist_ok=True)

# 4) Настройки yt-dlp (без вывода прогресса)
YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "logger": logging.getLogger("yt-dlp"),
}

# ——————————————————————————————————————————————
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Привет! Я бот, скачиваю видео из YouTube, TikTok, Instagram, Pinterest.\n"
        "Просто отправь ссылку. Максимум 50 МБ для отправки в чат,\n"
        "если больше — дам прямую ссылку на скачивание."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Отправь, пожалуйста, **корректную** ссылку.")

    status = await message.reply("⏳ Скачиваю… это может занять до минуты")
    filename = None

    try:
        # heavy IO in thread
        def yt_download():
            with YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await asyncio.to_thread(yt_download)
        size = os.path.getsize(filename)
        logging.info(f"Downloaded {filename} ({size} bytes)")

        if size <= 50 * 1024 * 1024:
            video = FSInputFile(filename)
            await message.reply_video(video)
        else:
            base = WEBHOOK_URL.rsplit("/webhook", 1)[0]
            public_url = f"{base}/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Видео скачано ({size//1024**2} МБ), но слишком большое для Telegram.\n"
                f"Скачать можно здесь:\n{public_url}"
            )
    except Exception as e:
        logging.exception("Ошибка при скачивании/отправке")
        await message.reply(f"❌ Ошибка:\n`{e}`", parse_mode="Markdown")
    finally:
        # удаляем статус и файл
        await status.delete()
        if filename and os.path.exists(filename):
            try: os.remove(filename)
            except: pass

# ——————————————————————————————————————————————
async def on_startup():
    logging.info("▶️ Регистрирую webhook")
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown():
    logging.info("🛑 Удаляю webhook")
    await bot.delete_webhook()
    await bot.session.close()

# ——————————————————————————————————————————————
if __name__ == "__main__":
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    app.on_startup.append(lambda _: asyncio.create_task(on_startup()))
    app.on_shutdown.append(lambda _: asyncio.create_task(on_shutdown()))
    # Статические файлы для больших видео
    app.router.add_static("/", DOWNLOADS, show_index=True)

    logging.info(f"🚀 Слушаю порт {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
