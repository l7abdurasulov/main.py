import os
import telebot
import yt_dlp

# Bot tokeningizni shu yerga yozing
TOKEN = "SIZNING_BOT_TOKENINGIZ"
bot = telebot.TeleBot(TOKEN)

# Yuklamalar uchun vaqtinchalik papka
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
  os.makedirs(DOWNLOAD_DIR)


@bot.message_handler(commands=["start"])
def send_welcome(message):
  bot.reply_to(
      message,
      "Assalomu alaykum! 🎵\n\n"
      "Menga:\n"
      "1. **Instagram** yoki **YouTube** havolasini yuboring — video yuklab beraman.\n"
      "2. **Qo'shiq nomi, ijrochi yoki matn parchasini** yuboring — musiqani topib beraman.",
      parse_mode="Markdown",
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  text = message.text.strip()
  chat_id = message.chat.id

  # 1. Instagram yoki YouTube havolasi kelganini tekshirish
  if "instagram.com" in text or "youtube.com" in text or "youtu.be" in text:
    msg = bot.send_message(
        chat_id, "⏳ Havola tekshirilmoqda va yuklab olinmoqda..."
    )
    try:
      ydl_opts = {
          "format": "best",
          "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
          "noplaylist": True,
      }

      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(text, download=True)
        filename = ydl.prepare_filename(info)

      bot.edit_message_text(
          "📤 Video yuborilmoqda...", chat_id, msg.message_id
      )

      with open(filename, "rb") as video_file:
        bot.send_video(chat_id, video_file)

      # Faylni o'chirib tashlash (server xotirasi to'lib qolmasligi uchun)
      if os.path.exists(filename):
        os.remove(filename)

      bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
      bot.edit_message_text(
          f"❌ Videoni yuklab olishda xatolik yuz berdi: {str(e)}",
          chat_id,
          msg.message_id,
      )

  # 2. Matn (Musiqa nomi yoki parchasi) kelgan bo'lsa
  else:
    msg = bot.send_message(
        chat_id, "🔍 Musiqa qidirilmoqda va yuklab olinmoqda..."
    )
    try:
      # YouTube orqali matn bo'yicha qidirish (Spotify vazifasini bajaradi)
      search_query = f"ytsearch1:{text}"

      ydl_opts = {
          "format": "bestaudio/best",
          "postprocessors": [{
              "key": "FFmpegExtractAudio",
              "preferredcodec": "mp3",
              "preferredquality": "192",
          }],
          "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
          "noplaylist": True,
      }

      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=True)
        if "entries" in info:
          info = info["entries"][0]

        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        mp3_filename = base + ".mp3"

      bot.edit_message_text(
          "🎵 Musiqa yuborilmoqda...", chat_id, msg.message_id
      )

      with open(mp3_filename, "rb") as audio_file:
        bot.send_audio(
            chat_id,
            audio_file,
            title=info.get("title", "Musiqa"),
            performer=info.get("uploader", "Noma'lum artist"),
        )

      # Faylni o'chirish
      if os.path.exists(mp3_filename):
        os.remove(mp3_filename)

      bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
      bot.edit_message_text(
          f"❌ Musiqani topib bo'lmadi yoki xatolik yuz berdi: {str(e)}",
          chat_id,
          msg.message_id,
      )


# Botni ishga tushirish
if __name__ == "__main__":
  print("Bot ishga tushdi...")
  bot.infinity_polling()
