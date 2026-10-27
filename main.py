import asyncio, os, subprocess, tempfile
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (Message, CallbackQuery, FSInputFile,
                           InlineKeyboardMarkup, InlineKeyboardButton)
import yt_dlp
import imageio_ffmpeg
from shazamio import Shazam
 
BOT_TOKEN = os.environ["BOT_TOKEN"]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
LIMIT = 49 * 1024 * 1024          # Telegram bot fayl limiti ~50 MB
HOSTS = ("instagram.com", "youtube.com", "youtu.be")
 
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
 
 
# ---------- yt-dlp yordamchilari ----------
def base_opts(outtmpl=None):
    o = {"quiet": True, "noplaylist": True, "ffmpeg_location": FFMPEG}
    if outtmpl:
        o["outtmpl"] = outtmpl
    if os.path.exists("cookies.txt"):      # Instagram uchun kerak bo'lishi mumkin
        o["cookiefile"] = "cookies.txt"
    return o
 
 
def download_video(url, folder):
    o = base_opts(f"{folder}/%(id)s.%(ext)s")
    o["format"] = ("b[filesize<49M][ext=mp4]/b[filesize_approx<49M][ext=mp4]/"
                   "b[height<=480]/b")
    with yt_dlp.YoutubeDL(o) as y:
        info = y.extract_info(url, download=True)
        return y.prepare_filename(info), info.get("title") or ""
 
 
def download_audio(video_id, folder):
    o = base_opts(f"{folder}/%(id)s.%(ext)s")
    o["format"] = "bestaudio/best"
    o["postprocessors"] = [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192"}]
    with yt_dlp.YoutubeDL(o) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={video_id}",
                              download=True)
        return f"{folder}/{info['id']}.mp3", info.get("title") or ""
 
 
def search_yt(query, n=5):
    o = base_opts()
    o["extract_flat"] = True
    with yt_dlp.YoutubeDL(o) as y:
        info = y.extract_info(f"ytsearch{n}:{query}", download=False)
    return [(e["id"], e.get("title") or "") for e in info.get("entries", []) if e]
 
 
# ---------- musiqani aniqlash ----------
def extract_clip(video_path, out_path):
    subprocess.run([FFMPEG, "-y", "-i", video_path, "-t", "20", "-vn",
                    "-ac", "1", "-ar", "44100", out_path],
                   check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
 
 
async def recognize(path):
    out = await Shazam().recognize(path)
    t = out.get("track")
    if not t:
        return None
    return t.get("title", ""), t.get("subtitle", "")
 
 
# ---------- handlerlar ----------
@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Salom! 👋\n\n"
        "🎬 Instagram yoki YouTube havolasini yuboring, video yuklab beraman "
        "va ichidagi musiqani topaman.\n"
        "🎵 Qo'shiq nomi, ijrochi yoki matndan parcha yozing, musiqani topib beraman."
    )
 
 
@dp.message(F.text.contains("http"))
async def on_link(m: Message):
    url = next((w for w in m.text.split() if w.startswith("http")), "")
    if not any(h in url for h in HOSTS):
        return await m.answer("Hozircha faqat Instagram va YouTube havolalari.")
    wait = await m.answer("⏳ Yuklanmoqda...")
    try:
        with tempfile.TemporaryDirectory() as d:
            path, title = await asyncio.to_thread(download_video, url, d)
            if os.path.getsize(path) > LIMIT:
                return await m.answer("Video 50 MB dan katta, Telegram orqali yuborib bo'lmaydi.")
            await m.answer_video(FSInputFile(path), caption=title[:200])
 
            # videodagi musiqani aniqlash
            try:
                clip = f"{d}/clip.wav"
                await asyncio.to_thread(extract_clip, path, clip)
                res = await recognize(clip)
            except Exception as e:
                print("recognize error:", e)
                res = None
 
            if not res:
                return await m.answer("🎵 Musiqa aniqlanmadi.")
            name, artist = res
            found = await asyncio.to_thread(search_yt, f"{artist} {name}", 1)
            text = f"🎵 {artist} — {name}"
            if found:
                kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬇️ MP3 yuklab olish",
                                         callback_data=f"a:{found[0][0]}")]])
                await m.answer(text, reply_markup=kb)
            else:
                await m.answer(text)
    except Exception as e:
        print("ERR:", e)
        await m.answer("Yuklab bo'lmadi. Havola ochiq (private emas) ekanini tekshiring.")
    finally:
        await wait.delete()
 
 
@dp.message(F.text & ~F.text.startswith("/"))
async def on_query(m: Message):
    wait = await m.answer("🔎 Qidirilmoqda...")
    try:
        res = await asyncio.to_thread(search_yt, m.text, 5)
        if not res:
            return await m.answer("Hech narsa topilmadi.")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{i}. {t[:55]}", callback_data=f"a:{vid}")]
            for i, (vid, t) in enumerate(res, 1)])
        await m.answer("Topilganlar, tanlang 👇", reply_markup=kb)
    except Exception as e:
        print("ERR:", e)
        await m.answer("Qidirishda xatolik bo'ldi.")
    finally:
        await wait.delete()
 
 
@dp.callback_query(F.data.startswith("a:"))
async def on_audio(c: CallbackQuery):
    await c.answer("⏳ Yuklanmoqda...")
    vid = c.data[2:]
    try:
        with tempfile.TemporaryDirectory() as d:
            path, title = await asyncio.to_thread(download_audio, vid, d)
            if os.path.getsize(path) > LIMIT:
                return await c.message.answer("Fayl juda katta.")
            await c.message.answer_audio(FSInputFile(path), title=title[:100])
    except Exception as e:
        print("ERR:", e)
        await c.message.answer("MP3 yuklab bo'lmadi.")
 
 
async def main():
    await dp.start_polling(bot)
 
 
if __name__ == "__main__":
    asyncio.run(main())
 
