import os
import telebot
import yt_dlp

# Bot tokenini muhit o'zgaruvchisidan oladi
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    print("Diqqat: BOT_TOKEN topilmadi! Render yoki hosting sozlamalarini tekshiring.")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "Salom! 👋\n"
        "Menga **YouTube** yoki **Instagram** havolasini yuboring, men sizga o'sha media uchun barcha yuklab olish havolalarini topib beraman! 🎬🎵"
    )

@bot.message_handler(func=lambda message: message.text and ('youtube.com' in message.text or 'youtu.be' in message.text or 'instagram.com' in message.text))
def get_media_links(message):
    url = message.text.strip()
    processing_msg = bot.reply_to(message, "🔍 Havolalar tahlil qilinmoqda, iltimos kuting...")
    
    ydl_opts = {
        'noplaylist': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            title = info.get('title', 'Nomaʼlum media')
            duration = info.get('duration_string', 'Nomaʼlum')
            uploader = info.get('uploader', 'Nomaʼlum')
            formats = info.get('formats', [])
            
            response_text = f"<b>📥 Topilgan media ma'lumotlari:</b>\n\n" \
                            f"📌 <b>Sarlavha:</b> {title}\n" \
                            f"👤 <b>Muallif:</b> {uploader}\n" \
                            f"⏱ <b>Davomiyligi:</b> {duration}\n\n" \
                            f"🔗 <b>To'g'ridan-to'g'ri havolalar:</b>\n"
            
            count = 0
            for f in formats:
                if f.get('url') and f.get('ext') in ['mp4', 'm4a', 'mp3']:
                    quality = f.get('format_note') or f.get('resolution') or 'Standart'
                    ext = f.get('ext')
                    file_url = f.get('url')
                    
                    if ext == 'mp4' and quality != 'unknown':
                        response_text += f"• <a href='{file_url}'>Video ({quality} - {ext})</a>\n"
                        count += 1
                    elif ext in ['m4a', 'mp3'] and count < 10:
                        response_text += f"• <a href='{file_url}'>Audio ({ext})</a>\n"
                        count += 1
                        
                    if count >= 6:
                        break

            if count == 0:
                response_text += "Kechirasiz, to'g'ridan-to'g'ri havola topilmadi."

        bot.edit_message_text(
            response_text,
            message.chat.id,
            processing_msg.message_id,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ Xatolik yuz berdi. Havola yopiq yoki mavjud emas.\nSabab: {str(e)[:100]}",
            message.chat.id,
            processing_msg.message_id
        )

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "Iltimos, faqat **YouTube** yoki **Instagram** havolasini yuboring! 🔗")

if __name__ == '__main__':
    print("Bot to'xtovsiz ishga tushmoqda...")
    # Eski webhook'ni majburiy o'chirish (409 xatoligini oldini oladi)
    bot.remove_webhook()
    bot.infinity_polling(skip_pending=True)
