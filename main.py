import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from aiohttp import web
import yt_dlp

TOKEN = "8804588411:AAFV2AYGA0dwKBBgJ0TCqCgyBXAscqqOyks"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# 1. Start bosganda foydalanuvchi ismi bilan murojaat qilish
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_name = message.from_user.first_name
    await message.answer(
        f"Assalomu alaykum, {user_name}! Men video yuklab beruvchi botman.\n\n"
        "Menga Instagram, YouTube yoki TikTok havolasini yuboring, videoni yuklab beraman!"
    )

@dp.message(F.text.startswith("http"))
async def download_video(message: Message):
    url = message.text.strip()
    processing_msg = await message.answer("⏳ Video yuklab olinmoqda, iltimos kuting...")
    
    output_filename = "downloaded_video.mp4"
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_filename,
        'max_filesize': 50 * 1024 * 1024,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_filename):
            video_file = FSInputFile(output_filename)
            await message.answer_video(video=video_file, caption="Mana siz so'ragan video! 📥")
            await processing_msg.delete()
            os.remove(output_filename)
        else:
            await processing_msg.edit_text("❌ Videoni yuklab olishning iloji bo'lmadi.")
            
    except Exception as e:
        logging.error(f"Xato: {e}")
        await processing_msg.edit_text("❌ Xatolik yuz berdi. Havola yoki video hajmini tekshiring.")
        if os.path.exists(output_filename):
            os.remove(output_filename)

# 2. Render uchun kichik veb-server (Portni band qilish uchun)
async def handle(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

async def main():
    # Veb-serverni ishga tushiramiz
    await web_server()
    # Bot pollingni boshlaymiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
