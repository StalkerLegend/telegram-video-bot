import os
import logging
import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

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

# 4) Опции yt-dlp с обходом региональных ограничений и корректным UA
YDL_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": f"{DOWNLOADS}/%(title).50s.%(ext)s",
    "noplaylist": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    },
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
        return await message.reply("❗ Пожалуйста, отправь корректную ссылку.")

    # Преобразование YouTube Shorts в обычный URL
    if "youtube.com/shorts/" in url:
        video_id = url.rstrip("/").split("/")[-1]
        url = f"https://www.youtube.com/watch?v={video_id}"

    status = await message.reply("⏳ Проверяю и скачиваю… это может занять минуту")
    filename = None

    try:
        # DEBUG: проверка метаданных
        info = await asyncio.to_thread(
            lambda: YoutubeDL({**YDL_OPTS, "skip_download": True}).extract_info(url, download=False)
        )
        logging.info(f"YT-DLP info: title={info.get('title')}, formats={len(info.get('formats', []))}")

        # Функция для реального скачивания
        def yt_download():
            with YoutubeDL(YDL_OPTS) as ydl:
                data = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(data)

        # Запуск в отдельном потоке
        filename = await asyncio.to_thread(yt_download)
        size = os.path.getsize(filename)
        logging.info(f"Downloaded {filename}, size={size} bytes")

        if size <= 50 * 1024 * 1024:
            await message.reply_video(FSInputFile(filename))
        else:
            base = f"https://{os.getenv('RENDER_SERVICE_NAME')}.onrender.com"
            public = f"{base}/{os.path.basename(filename)}"
            await message.reply(
                f"✅ Скачано ({size//1024**2} МБ), но слишком большой файл для Telegram.\n"
                f"Скачать здесь:\n{public}"
            )

    except DownloadError:
        logging.warning("Видео недоступно (DownloadError).")
        await message.reply("⚠️ К сожалению, это видео недоступно для скачивания.")
    except ExtractorError:
        logging.warning("Ошибка извлечения форматов (ExtractorError).")
        await message.reply("❗ Не удалось извлечь информацию о видео. Проверь ссылку.")
    except Exception as e:
        logging.exception("Ошибка при загрузке/отправке видео:")
        await message.reply(f"❌ Произошла ошибка:\n`{e}`", parse_mode="Markdown")
    finally:
        # удаляем статус и временный файл
        await status.delete()
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass

# ——————————————————————————————————————————————
async def init_http():
    app = web.Application()
    # health-check
    async def health(request):
        return web.Response(text="OK")
    app.router.add_get("/", health)
    # отдаём скачанные файлы
    app.router.add_static("/", DOWNLOADS, show_index=True)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"🚀 HTTP server listening on port {PORT}")

# ——————————————————————————————————————————————
async def main():
    # сбрасываем любые webhook от предыдущих запусков
    await bot.delete_webhook(drop_pending_updates=True)
    # старт HTTP и polling параллельно
    await init_http()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
