import json
import logging
import os
import threading
import time
from flask import Flask
import requests
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import yt_dlp

# --- 1. LOGLARNI SOZLASH ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- 2. FLASK SERVERI (Render 24/7 ishlashi uchun) ---
app = Flask(__name__)


@app.route('/')
def home():
  return 'Bot 24/7 rejimida mukammal ishlamoqda!'


# --- 3. TELEGRAM BOTNI SOZLASH ---
TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))

# 📌 MAJBURIY OBUNA UCHUN KANAL USERNAME'I (Masalan: '@kanalungiz')
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@kanalungiz')

# 📌 BOTNING O'ZGARMAS USERNAME'I (@ belgisisiz)
BOT_USERNAME = 'MediaDownloaderBot'

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

try:
  bot.remove_webhook()
except Exception:
  pass

user_data = {}
USERS_FILE = 'users.json'


def load_users():
  """Foydalanuvchilar bazasini yuklash"""
  if os.path.exists(USERS_FILE):
    try:
      with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return set(json.load(f))
    except Exception as e:
      logger.error(f'Bazani o‘qishda xatolik: {e}')
      return set()
  return set()


def save_user(user_id):
  """Yangi foydalanuvchini maxfiy bazaga qo'shish"""
  users = load_users()
  if user_id not in users:
    users.add(user_id)
    try:
      with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(users), f)
    except Exception as e:
      logger.error(f'Foydalanuvchini saqlashda xatolik: {e}')


def check_subscription(user_id):
  """Tune Hunt uslubidagi majburiy obunani tekshirish"""
  if not CHANNEL_USERNAME or CHANNEL_USERNAME == '@kanalungiz':
    return True  # Agar kanal kiritilmagan bo'lsa, tekshirmaydi
  try:
    member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
    if member.status in ['member', 'administrator', 'creator']:
      return True
  except Exception as e:
    logger.error(f'Obunani tekshirish xatosi: {e}')
  return False


def get_subscription_markup():
  """Kanalga obuna bo'lish tugmasi"""
  markup = InlineKeyboardMarkup(row_width=1)
  channel_link = (
      f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
      if not CHANNEL_USERNAME.startswith('http')
      else CHANNEL_USERNAME
  )
  markup.add(
      InlineKeyboardButton(
          '📢 Kanalga a’zo bo‘lish', url=channel_link
      ),
      InlineKeyboardButton(
          '🔄 Tekshirish', callback_data='check_sub'
      ),
  )
  return markup


# --- 4. START VA OBUNANI TEKSHIRISH ---
@bot.message_handler(commands=['start'])
def start_command(message):
  user_id = message.from_user.id
  user_name = message.from_user.first_name
  save_user(user_id)

  if not check_subscription(user_id):
    bot.send_message(
        message.chat.id,
        f'<b>❌ Botdan foydalanish uchun avval kanalimizga a’zo bo‘lishingiz kerak!</b>\n\n'
        f'Kanalga a’zo bo‘lib, <b>"🔄 Tekshirish"</b> tugmasini bosing.',
        reply_markup=get_subscription_markup(),
    )
    return

  start_text = (
      f'⚡️ Assalomu alaykum, <b>{user_name}</b>!\n\n'
      f'🤖 <b>Universal Media Downloader & Shazam Bot</b>ga xush kelibsiz.\n\n'
      f'📥 <b>Qo‘llab-quvvatlanadigan tarmoqlar:</b>\n'
      f'• Instagram (Post, IGTV)\n'
      f'• TikTok & Likee & Snapchat (Suv belgisiz video)\n'
      f'• YouTube (Video va Shorts)\n'
      f'• Pinterest (Video va rasmlar)\n\n'
      f'🎵 Shuningdek, qo‘shiq nomini yuborib yoki audio/ovozli xabar tashlab Shazam qilishingiz mumkin!'
  )
  bot.reply_to(message, start_text)


@bot.callback_query_handler(
    func=lambda call: call.data == 'check_sub'
)
def callback_check_sub(call):
  user_id = call.from_user.id
  if check_subscription(user_id):
    bot.answer_callback_query(call.id, '✅ Rahmat! Obuna tasdiqlandi.')
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
      pass
    bot.send_message(
        call.message.chat.id,
        '🎉 Tabriklayman! Endi istalgan video havolasini yoki qo‘shiq nomini yuborishingiz mumkin.',
    )
  else:
    bot.answer_callback_query(
        call.id,
        '❌ Siz hali kanalga a’zo bo‘lmadingiz!',
        show_alert=True,
    )


# --- 5. ADMIN STATISTIKA VA BROADCAST ---
@bot.message_handler(commands=['stats'])
def stats_command(message):
  user_id = message.from_user.id
  if ADMIN_ID == 0 or user_id == ADMIN_ID:
    users_count = len(load_users())
    bot.reply_to(
        message,
        f'📊 <b>Bot statistikasi:</b>\n\n👥 Jami foydalanuvchilar: <b>{users_count}</b> ta',
    )
  else:
    bot.reply_to(message, '❌ Bu buyruq faqat bot admini uchun!')


@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
  user_id = message.from_user.id
  if ADMIN_ID != 0 and user_id != ADMIN_ID:
    bot.reply_to(message, '❌ Bu buyruq faqat admin uchun!')
    return

  text_to_send = message.text.replace('/broadcast', '').strip()
  if not text_to_send:
    bot.reply_to(
        message,
        '⚠️ Xabar matni kiritilmadi!\nIshlatilishi: <code>/broadcast Xabar matni</code>',
    )
    return

  users = load_users()
  success = 0
  failed = 0

  status_msg = bot.reply_to(
      message,
      f'📢 Xabar tarqatish boshlandi... Jami foydalanuvchilar: {len(users)} ta',
  )

  for uid in users:
    try:
      bot.send_message(uid, f'📢 <b>E’lon:</b>\n\n{text_to_send}')
      success += 1
      time.sleep(0.1)
    except Exception:
      failed += 1

  bot.edit_message_text(
      f'✅ <b>Xabar tarqatish yakunlandi!</b>\n\n'
      f'• Muvaffaqiyatli: {success} ta\n'
      f'• Xatoliklar (bloklaganlar): {failed} ta',
      message.chat.id,
      status_msg.message_id,
  )


# --- 6. MEDIA YUKLASH (YouTube, Instagram, TikTok, Snapchat, Likee, Pinterest) ---
ydl_video_opts = {
    'format': 'best',
    'outtmpl': 'downloads/%(id)s.%(ext)s',
    'noplaylist': True,
    'quiet': True,
}


@bot.message_handler(
    func=lambda message: message.text
    and message.text.strip().startswith('http')
)
def handle_media(message):
  user_id = message.from_user.id
  save_user(user_id)

  if not check_subscription(user_id):
    bot.reply_to(
        message,
        '<b>❌ Botdan foydalanish uchun avval kanalimizga a’zo bo‘ling!</b>',
        reply_markup=get_subscription_markup(),
    )
    return

  chat_id = message.chat.id
  url = message.text.strip()
  status_msg = bot.send_message(
      chat_id, '📥 <b>Yuklanmoqda...</b>\nIltimos, biroz kuting ⏳'
  )
  file_path = None

  try:
    os.makedirs('downloads', exist_ok=True)

    with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
      info = ydl.extract_info(url, download=True)
      if 'entries' in info:
        info = info['entries'][0]
      file_path = ydl.prepare_filename(info)

    if not file_path or not os.path.exists(file_path):
      raise Exception('Faylni yuklab bo‘lmadi.')

    title = info.get('title', 'Media')
    description = info.get('description', '')

    user_data[chat_id] = {'url': url, 'title': title, 'lyrics': description}

    markup = InlineKeyboardMarkup(row_width=1)
    btn_audio = InlineKeyboardButton(
        '🎧 Musiqa (Audio)', callback_data='get_audio'
    )
    btn_lyrics = InlineKeyboardButton(
        '📝 Qo‘shiq so‘zlari', callback_data='get_lyrics'
    )
    markup.add(btn_audio, btn_lyrics)

    caption = (
        f'🎬 <b>{title[:60]}</b>\n\n'
        f'📥 <i>@{BOT_USERNAME} orqali yuklab olindi</i>'
    )

    with open(file_path, 'rb') as media_file:
      if file_path.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        bot.send_photo(
            chat_id=chat_id,
            photo=media_file,
            caption=caption,
            reply_markup=markup,
        )
      else:
        bot.send_video(
            chat_id=chat_id,
            video=media_file,
            caption=caption,
            reply_markup=markup,
        )

    try:
      bot.delete_message(chat_id, status_msg.message_id)
    except Exception:
      pass

  except Exception as e:
    logger.error(f'Yuklash xatoligi: {e}')
    try:
      bot.edit_message_text(
          '❌ <b>Xatolik yuz berdi:</b>\nHavolani tekshiring yoki boshqa havola yuboring.',
          chat_id,
          status_msg.message_id,
      )
    except Exception:
      pass

  finally:
    if file_path and os.path.exists(file_path):
      try:
        os.remove(file_path)
      except Exception:
        pass


# --- 7. SHAZAM FUNKSIYASI ---
@bot.message_handler(
    content_types=['text', 'audio', 'voice', 'video', 'video_note']
)
def handle_shazam_and_search(message):
  if message.text and message.text.startswith('http'):
    return

  user_id = message.from_user.id
  save_user(user_id)

  if not check_subscription(user_id):
    bot.reply_to(
        message,
        '<b>❌ Botdan foydalanish uchun avval kanalimizga a’zo bo‘ling!</b>',
        reply_markup=get_subscription_markup(),
    )
    return

  chat_id = message.chat.id
  query = ''
  if message.text and not message.text.startswith('/'):
    query = message.text.strip()
  elif message.audio:
    query = (
        f"{message.audio.performer or ''} {message.audio.title or ''}".strip()
    )
    if not query:
      query = 'Popular song'
  elif message.voice:
    query = 'Voice search track'
  elif message.video or message.video_note:
    query = 'Video search track'

  if not query:
    return

  status_msg = bot.send_message(
      chat_id,
      '🔍 <b>Shazam / Qidirilmoqda...</b>\nQo‘shiq qidirilmoqda 🎶',
  )

  try:
    search_opts = {
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1',
        'outtmpl': 'downloads/%(id)s_shazam.%(ext)s',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(search_opts) as ydl:
      info = ydl.extract_info(query, download=True)
      if 'entries' in info:
        info = info['entries'][0]
      audio_path = ydl.prepare_filename(info)

    title = info.get('title', 'Topilgan qo‘shiq')
    uploader = info.get('uploader', 'Noma’lum ijrochi')
    description = info.get('description', 'Qo‘shiq matni mavjud emas.')

    clean_lyrics = (
        description[:1500] + '...'
        if len(description) > 1500
        else description
    )

    with open(audio_path, 'rb') as audio_file:
      bot.send_audio(
          chat_id=chat_id,
          audio=audio_file,
          title=title,
          performer=uploader,
          caption=(
              f'🎵 <b>Topilgan qo‘shiq:</b> {title}\n🎤 <b>Ijrochi:</b>'
              f' {uploader}\n\n📝 <b>Matn parchasi:</b>\n<i>{clean_lyrics}</i>'
          ),
      )

    try:
      bot.delete_message(chat_id, status_msg.message_id)
    except Exception:
      pass

    if os.path.exists(audio_path):
      os.remove(audio_path)

  except Exception as e:
    logger.error(f'Shazam xatoligi: {e}')
    try:
      bot.edit_message_text(
          '❌ <b>Topilmadi:</b> Ushbu so‘rov bo‘yicha hech narsa topilmadi.',
          chat_id,
          status_msg.message_id,
      )
    except Exception:
      pass


# --- 8. CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
  if call.data == 'check_sub':
    return

  chat_id = call.message.chat.id
  data = user_data.get(chat_id)

  if not data:
    bot.answer_callback_query(
        call.id,
        '❌ Ma’lumot topilmadi, qaytadan havola yuboring.',
        show_alert=True,
    )
    return

  if call.data == 'get_audio':
    bot.answer_callback_query(call.id, '🎧 Musiqa tayyorlanmoqda...')
    audio_msg = bot.send_message(chat_id, '⏳ <b>Audio yuklab olinmoqda...</b>')

    audio_path = None
    try:
      ydl_audio_opts = {
          'format': 'bestaudio/best',
          'outtmpl': 'downloads/%(id)s_audio.%(ext)s',
          'noplaylist': True,
          'quiet': True,
      }

      with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
        info = yt_dlp.YoutubeDL(ydl_audio_opts).extract_info(
            data['url'], download=True
        )
        if 'entries' in info:
          info = info['entries'][0]
        audio_path = ydl.prepare_filename(info)

      title = info.get('title', 'Audio')
      uploader = info.get('uploader', 'Artist')

      with open(audio_path, 'rb') as audio_file:
        bot.send_audio(
            chat_id=chat_id,
            audio=audio_file,
            title=title,
            performer=uploader,
            caption=(
                f'🎧 <b>{title}</b>\n\n📥 <i>@{BOT_USERNAME} orqali yuklab'
                ' olindi</i>'
            ),
        )

      try:
        bot.delete_message(chat_id, audio_msg.message_id)
      except Exception:
        pass

    except Exception as e:
      logger.error(f'Audio yuklash xatosi: {e}')
      try:
        bot.edit_message_text(
            '❌ <b>Audio faylni yuklab bo‘lmadi.</b>',
            chat_id,
            audio_msg.message_id,
        )
      except Exception:
        pass
    finally:
      if audio_path and os.path.exists(audio_path):
        try:
          os.remove(audio_path)
        except Exception:
          pass

  elif call.data == 'get_lyrics':
    lyrics = data.get('lyrics')
    if lyrics and len(lyrics.strip()) > 0:
      clean_lyrics = lyrics[:2000] + '...' if len(lyrics) > 2000 else lyrics
      bot.send_message(
          chat_id,
          f'🎤 <b>Qo‘shiq so‘zlari:</b>\n\n<i>{clean_lyrics}</i>',
      )
    else:
      bot.answer_callback_query(
          call.id, '❌ Ushbu media uchun so‘zlar topilmadi.', show_alert=True
      )


# --- 9. BACKGROUND OQIMLAR (24/7) ---
def run_telegram_bot():
  while True:
    try:
      logger.info('Telegram bot polling ishga tushdi...')
      bot.infinity_polling(
          none_stop=True, interval=2, timeout=60, long_polling_timeout=60
      )
    except Exception as e:
      logger.error(f'Polling xatosi: {e}')
      time.sleep(5)


def run_keep_alive():
  RENDER_URL = 'https://my-bot-6xmi.onrender.com'
  while True:
    time.sleep(300)
    try:
      requests.get(RENDER_URL, timeout=10)
      logger.info('Self-ping bajarildi.')
    except Exception as e:
      logger.warning(f'Ping xatosi: {e}')


if __name__ == '__main__':
  bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
  bot_thread.start()

  ping_thread = threading.Thread(target=run_keep_alive, daemon=True)
  ping_thread.start()

  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
