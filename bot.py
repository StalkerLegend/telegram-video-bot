import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from yt_dlp import YoutubeDL

# —————————————————————————————————————————————————————————————————————————————
#  1) DEBUG и логи
logging.basicConfig(level=logging.INFO)

#  2) Конфигурация из переменных окружения
BOT_TOKEN   = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")   # https://<your-service>.onrender.com/webhook
PORT        = int(os.getenv("PORT", 8443))  # Telegram принимает 443,80,88,8443
DOWNLOADS   = "downloads"

if not BOT_TOKEN or not WEBHOOK_URL:
    logging.error("❌ Задайте в ENV BOT_TOKEN и WEBHOOK_URL!")
    exit(1)

#  3) Инициализация
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

#  4) Папка для видео
os.makedirs(DOWNLOADS, exist_ok=True)

#  5) Опции yt-dlp
YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
}

# —————————————————————————————————————————————————————————————————————————————
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Я бот для скачивания видео.\n"
        "Отправь ссылку (YouTube, TikTok, Instagram, Pinterest).\n"
        "⚠️ Макс. размер для Telegram: 50 МБ."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Пожалуйста, отправь корректную ссылку.")

    status = await message.reply("⏳ Скачиваю…")
    filename = None

    try:
        # 1) Скачиваем
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        # 2) Проверяем размер
        size = os.path.getsize(filename)
        if size <= 50 * 1024 * 1024:
            video = InputFile(path_or_bytesio=filename)
            await message.reply_video(video)
        else:
            await message.reply(
                f"✅ Скачал, но он слишком большой ({size//1024**2} МБ).\n"
                f"Скачать можно по ссылке:\n"
                f"`{WEBHOOK_URL.replace('/webhook','')}/{os.path.basename(filename)}`",
                parse_mode="Markdown"
            )
    except Exception as e:
        logging.exception("Ошибка при скачивании/отправке:")
        await message.reply(f"❌ Произошла ошибка: {e}")
    finally:
        # 3) Удаляем файл
        if filename and os.path.exists(filename):
            os.remove(filename)

# —————————————————————————————————————————————————————————————————————————————
# Webhook: регистрируем на старте и удаляем на завершении
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown():
    await bot.delete_webhook()
    await bot.session.close()

# —————————————————————————————————————————————————————————————————————————————
if __name__ == "__main__":
    # 1) Создаём aiohttp-приложение
    app = web.Application()
    # 2) Регистрируем обработчик Telegram-webhook
    SimpleRequestHandler(dispatcher=dp).register(app, path="/webhook")
    # 3) Регистрация хуков
    app.on_startup.append(lambda app: on_startup())
    app.on_shutdown.append(lambda app: on_shutdown())
    # 4) Статика: отдаём скачанные файлы по HTTP
    app.router.add_static("/", DOWNLOADS, show_index=True)

    # 5) Старт сервера
    logging.info(f"🚀 Запускаем на порту {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)
