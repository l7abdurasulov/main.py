import os, re, asyncio, glob, shutil, tempfile
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
from shazamio import Shazam

TOKEN = os.environ["BOT_TOKEN"]
COOKIES = os.environ.get("COOKIES_FILE")  # ixtiyoriy: cookies.txt yo'li
URL_RE = re.compile(r"https?://\S+")

bot = Bot(TOKEN)
dp = Dispatcher()
sem = asyncio.Semaphore(4)  # bir vaqtda 4 ta yuklash
urls = {}  # message_id -> havola


def dl(query, kind, folder):
    o = {
        "outtmpl": f"{folder}/%(title).60s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 3,
        "concurrent_fragment_downloads": 8,
        "max_filesize": 50 * 1024 * 1024,  # Telegram bot limiti
        "format": "bestaudio[ext=m4a]/bestaudio" if kind == "a"
        else "best[ext=mp4][filesize<50M]/best[ext=mp4]/best",
    }
    if COOKIES and os.path.exists(COOKIES):
        o["cookiefile"] = COOKIES
    with YoutubeDL(o) as y:
        y.download([query])
    files = glob.glob(f"{folder}/*")
    return files[0] if files else None


def run(fn, *a):
    return asyncio.get_running_loop().run_in_executor(None, fn, *a)


async def send_song(msg: Message, query, title=None, artist=None):
    folder = tempfile.mkdtemp()
    try:
        async with sem:
            path = await run(dl, f"ytsearch1:{query}", "a", folder)
        if not path:
            return await msg.answer("❌ Qo'shiq yuklanmadi.")
        await msg.answer_audio(FSInputFile(path), title=title, performer=artist)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer(
        "Havola yuboring (Instagram, YouTube, TikTok, Snapchat, Pinterest, CapCut) "
        "yoki qo'shiq nomini yozing."
    )


@dp.message(F.text)
async def got(m: Message):
    t = m.text.strip()
    mo = URL_RE.search(t)
    if not mo:  # havola emas -> qo'shiq nomi
        st = await m.answer("🔎 Qidirilmoqda...")
        await send_song(m, t, title=t)
        return await st.delete()

    url = mo.group(0)
    st = await m.answer("⏳ Yuklanmoqda...")
    folder = tempfile.mkdtemp()
    try:
        async with sem:
            path = await run(dl, url, "v", folder)
        if not path:
            return await st.edit_text("❌ Topilmadi yoki fayl 50MB dan katta.")
        if len(urls) > 2000:
            urls.clear()
        urls[m.message_id] = url
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎵 Musiqani topish", callback_data=f"m:{m.message_id}")
        ]])
        await m.answer_video(FSInputFile(path), supports_streaming=True, reply_markup=kb)
        await st.delete()
    except Exception:
        await st.edit_text("❌ Xatolik. Havola to'g'riligini tekshiring.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@dp.callback_query(F.data.regexp(r"^m:\d+$"))
async def find_music(c: CallbackQuery):
    url = urls.get(int(c.data[2:]))
    if not url:
        return await c.answer("Havolani qaytadan yuboring", show_alert=True)
    await c.answer("🔎 Musiqa aniqlanmoqda...")
    folder = tempfile.mkdtemp()
    try:
        async with sem:
            clip = await run(dl, url, "a", folder)
            sh = Shazam()
            fn = getattr(sh, "recognize", None) or sh.recognize_song  # eski/yangi versiya
            res = await fn(clip) if clip else {}
        track = res.get("track")
        if not track:
            return await c.message.answer("❌ Musiqa aniqlanmadi.")
        title, artist = track["title"], track["subtitle"]
        await c.message.answer(f"🎶 {artist} — {title}")
        await send_song(c.message, f"{artist} - {title}", title, artist)
    except Exception:
        await c.message.answer("❌ Musiqani aniqlashda xatolik.")
    finally:
        shutil.rmtree(folder, ignore_errors=True)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
