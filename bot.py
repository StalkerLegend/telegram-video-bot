import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InputFile, Update
from aiogram.webhook.kp import get_new_configured_app  # встроенный aiohttp-сервер
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO)

# 1. Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например, https://<your-service>.onrender.com
PORT = int(os.getenv("PORT", 8000))

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Не заданы BOT_TOKEN или WEBHOOK_URL!")
    exit(1)

# 2. Настройка yt-dlp
YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": "downloads/%(title).30s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
}

os.makedirs("downloads", exist_ok=True)

# 3. Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Отправь мне ссылку на видео (YouTube, TikTok, Instagram, Pinterest).\n"
        "⚠️ Максимум 50 МБ. Если больше — верну только ссылку на скачанный файл."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Нужна корректная ссылка!")

    loading = await message.reply("⏳ Скачиваю, подожди…")
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        size = os.path.getsize(filename)
        if size <= 50 * 1024 * 1024:
            video = InputFile(path_or_bytesio=filename)
            await message.reply_video(video)
        else:
            await message.reply(
                f"✅ Скачано ({size//1024**2} МБ), но слишком большое для Telegram.\n"
                f"Скачать: `{WEBHOOK_URL}/files/{os.path.basename(filename)}`",
                parse_mode="Markdown"
            )
    except Exception as e:
        logging.exception("Ошибка при скачивании")
        await message.reply(f"❌ Ошибка: {e}")
    finally:
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)

async def on_startup():
    # регистрируем webhook в Telegram
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown():
    # снимаем webhook
    await bot.delete_webhook()
    await bot.session.close()

# 4. Создаём aiohttp-приложение и монтируем его
app = get_new_configured_app(
    dp=dp,
    path="/",                 # корень принимаемых запросов
    on_startup=[on_startup],
    on_shutdown=[on_shutdown]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
