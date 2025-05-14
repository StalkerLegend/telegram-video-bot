import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import yt_dlp

BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет! Отправь ссылку на видео из YouTube, TikTok или Instagram.")

@dp.message_handler()
async def download(message: types.Message):
    url = message.text.strip()
    await message.answer("Скачиваю видео...")

    ydl_opts = {
        'outtmpl': '%(title).30s.%(ext)s',
        'format': 'mp4/best',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        with open(filename, 'rb') as f:
            await message.reply_video(f)

        os.remove(filename)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
