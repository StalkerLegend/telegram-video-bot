import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO)

# ——————————————————————————————————————————————
# 1) Конфигурация
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT      = int(os.getenv("PORT", "8000"))
DOWNLOADS = "downloads"

if not BOT_TOKEN:
    logging.error("❌ Не задан BOT_TOKEN в ENV")
    exit(1)

# ——————————————————————————————————————————————
# 2) Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher()

# 3) Папка для скачивания
os.makedirs(DOWNLOADS, exist_ok=True)

# 4) Опции yt-dlp (выключаем всё лишнее)
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
        "👋 Я бот для скачивания видео из YouTube, TikTok, Instagram и Pinterest.\n"
        "Просто отправь ссылку, я верну файл (до 50 МБ) или ссылку на скачивание."
    )

@dp.message()
async def download_handler(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Отправь, пожалуйста, правильную ссылку.")

    status = await message.reply("⏳ Скачиваю… подожди минуту")
    filename = None

    try:
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
            # Адрес для прямой загрузки через aiohttp
            public = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Скачано ({size//1024**2} МБ), но файл большой для Telegram.\n"
                f"Скачать можно здесь:\n{public}"
            )
    except Exception as e:
        logging.exception("Ошибка при скачивании")
        await message.reply(f"❌ Не удалось скачать видео:\n`{e}`", parse_mode="Markdown")
    finally:
        await status.delete()
        if filename and os.path.exists(filename):
            os.remove(filename)

# ——————————————————————————————————————————————
# HTTP-приложение для Render: health-check и отдача скачанных файлов
async def init_http_server():
    app = web.Application()
    async def health(request): return web.Response(text="OK")
    app.router.add_get("/", health)
    app.router.add_static("/", DOWNLOADS, show_index=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🚀 HTTP server listening on port {PORT}")

# ——————————————————————————————————————————————
async def main():
    # 1) Старт HTTP-сервера
    await init_http_server()
    # 2) Старт long-polling бота
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
