import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, InputFile
from yt_dlp import YoutubeDL

# 1. Настройка логов
logging.basicConfig(level=logging.INFO)

# 2. Получение токена из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("Переменная окружения BOT_TOKEN не задана!")
    exit(1)

# 3. Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 4. Общие опции для yt-dlp
YDL_OPTS = {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "outtmpl": "downloads/%(title).50s.%(ext)s",
    "noplaylist": True,
    "quiet": True,
}

# Создадим папку для скачанных файлов
os.makedirs("downloads", exist_ok=True)

@dp.message(Command(commands=["start", "help"]))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Я бот, могу скачивать видео по ссылке из YouTube, TikTok, Instagram и Pinterest.\n\n"
        "Просто отправь мне ссылку на видео, и я верну файл.\n\n"
        "⚠️  Ограничение по размеру файла: **до 50 МБ** (Telegram API).\n"
        "Если видео больше — бот пришлёт тебе ссылку на скачанный файл."
    )

@dp.message()
async def download_video(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.reply("❗ Нужна ссылка, начинающаяся с http:// или https://")

    info = await message.reply("⏳ Скачиваю видео, это может занять время...")
    try:
        with YoutubeDL(YDL_OPTS) as ydl:
            data = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(data)

        size = os.path.getsize(filename)
        if size <= 50 * 1024 * 1024:  # ≤ 50 МБ
            video = InputFile(path_or_bytesio=filename)
            await message.reply_video(video)
        else:
            # если больше 50 МБ, отправляем только ссылку
            await message.reply(f"✅ Видео скачано, но слишком большое ({size//1024**2} МБ).\n"
                                f"Скачать файл можно здесь:\n```\n{os.path.abspath(filename)}\n```")
    except Exception as e:
        logging.exception("Ошибка при скачивании или отправке видео")
        await message.reply(f"❌ Произошла ошибка:\n`{e}`", parse_mode="Markdown")

    # удаляем файл после отправки или уведомления
    try:
        if os.path.exists(filename):
            os.remove(filename)
    except:
        pass

async def main():
    await dp.start_polling(bot, allowed_updates=bot.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
