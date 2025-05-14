import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import yt_dlp
import os

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())

@dp.message()
async def download_video(message: Message):
    url = message.text.strip()
    if not url.startswith("http"):
        await message.reply("Пожалуйста, отправь ссылку на видео.")
        return

    await message.reply("⏳ Скачиваю видео...")

    ydl_opts = {
        'outtmpl': 'video.%(ext)s',
        'format': 'mp4',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_file = ydl.prepare_filename(info)
        
        await message.reply_video(open(video_file, 'rb'))
        os.remove(video_file)

    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {str(e)}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
