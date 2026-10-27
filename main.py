import os
import asyncio
import logging
import yt_dlp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from shazamio import Shazam

# Telegram bot tokeningizni kiriting
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Vaqtinchalik fayllar saqlanadigan papka
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "👋 Salom! Men Instagram / YouTube havolalarini qabul qilaman.\n\n"
        "Manga Instagram Reel yoki post havolasini yuboring, men videoni yuklab beraman "
        "va ichidagi musiqani topib beraman!"
    )


async def download_media(url: str, user_id: int):
    """Instagram havolasidan video va audioni yuklab oladi."""
    base_path = os.path.join(DOWNLOAD_DIR, f"{user_id}")

    ydl_opts_video = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{base_path}_video.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    ydl_opts_audio = {
        'format': 'bestaudio/best',
        'outtmpl': f'{base_path}_audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    loop = asyncio.get_event_loop()

    # Video yuklab olish
    with yt_dlp.YoutubeDL(ydl_opts_video) as ydl:
        await loop.run_in_executor(None, lambda: ydl.download([url]))

    # Audio yuklab olish (Shazam uchun)
    with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
        await loop.run_in_executor(None, lambda: ydl.download([url]))

    video_file = None
    for file in os.listdir(DOWNLOAD_DIR):
        if file.startswith(f"{user_id}_video"):
            video_file = os.path.join(DOWNLOAD_DIR, file)
            break

    audio_file = os.path.join(DOWNLOAD_DIR, f"{user_id}_audio.mp3")

    return video_file, audio_file


@dp.message(F.text.startswith("http"))
async def process_link(message: types.Message):
    url = message.text.strip()
    status_msg = await message.answer("🔄 Video va audio yuklanmoqda, kuting...")

    try:
        user_id = message.from_user.id
        video_path, audio_path = await download_media(url, user_id)

        # 1. Videoni Telegram'ga yuborish
        if video_path and os.path.exists(video_path):
            video_input = FSInputFile(video_path)
            await message.answer_video(video=video_input, caption="📹 Yuklangan video")

        # 2. Shazam orqali musiqani aniqlash
        await status_msg.edit_text("🎵 Qo'shiq aniqlanmoqda...")
        shazam = Shazam()
        track_info = await shazam.recognize(audio_path)

        track = track_info.get("track")
        if track:
            title = track.get("title", "Noma'lum")
            artist = track.get("subtitle", "Noma'lum")

            caption = (
                f"🎵 Qo'shiq topildi!\n\n"
                f"📌 Nomi: {title}\n"
                f"🎤 Ijrochi: {artist}"
            )
            await message.answer(caption, parse_mode="Markdown")
        else:
            await message.answer("🎵 Musiqa aniqlanmadi.")

        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("❌ Videoni yuklab olishda yoki musiqani aniqlashda xatolik yuz berdi.")

    finally:
        # Ishlatib bo'lingan fayllarni o'chirib tashlash
        user_id = message.from_user.id
        for file in os.listdir(DOWNLOAD_DIR):
            if file.startswith(str(user_id)):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except Exception:
                    pass


async def main():
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
