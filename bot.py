import telebot
import sqlite3
import requests
import time
import os
import logging
from telebot import types

# --- 1. إعدادات السيرفر والتوثيق ---
# التوكن ومفتاح الذكاء الاصطناعي
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
MAIN_CHANNEL = "@Yemen_International_Library" # معرف القناة

# إعداد نظام السجلات (Log) لمراقبة البوت في Railway
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# --- 2. إعداد قاعدة البيانات (مسار آمن) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'library.db')

def get_db_connection():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS books (name TEXT PRIMARY KEY, date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    return conn, cur

# --- 3. المخ (الذكاء الاصطناعي - Gemini) ---
def get_ai_description(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
    # هندسة الأوامر (Prompt Engineering) للحصول على سجع قوي
    prompt_text = (
        f"تخيل أنك أديب عربي فصيح في مكتبة عريقة. "
        f"اكتب وصفاً جذاباً جداً ومسجوعاً (سجعاً بليغاً) في سطرين فقط للكتاب المعنون: '{book_name}'. "
        f"ابدأ بكلمات قوية ولا تذكر اسم الكتاب في الوصف."
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 100}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error(f"AI Error: {e}")
        # وصف احتياطي بليغ في حال تعطل الذكاء الاصطناعي
        return "سفرٌ نفيس، فيه من العلم ما هو أنيس، وللعقل خير جليس."

# --- 4. قلب البوت (معالجة الملفات) ---
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_files(message):
    try:
        conn, cur = get_db_connection()
        
        # استخراج الاسم بذكاء
        file_name = "كتاب_جديد"
        if message.document:
            file_name = message.document.file_name
        elif message.caption:
            file_name = message.caption
        elif message.audio:
            file_name = f"{message.audio.performer} - {message.audio.title}"
            
        # تنظيف الاسم
        clean_name = str(file_name).replace('.pdf', '').replace('.epub', '').replace('.docx', '').replace('_', ' ').strip()
        
        logger.info(f"Receiving file: {clean_name}")

        # التحقق من التكرار
        cur.execute("SELECT name FROM books WHERE name=?", (clean_name,))
        if cur.fetchone():
            bot.reply_to(message, f"⚠️ **تنبيه:** هذا الكتاب 『 {clean_name} 』 موجود مسبقاً في الأرشيف!", parse_mode="Markdown")
            conn.close()
            return

        # رسالة انتظار
        wait_msg = bot.reply_to(message, "⏳ **جاري الفحص البلاغي والأرشفة...**", parse_mode="Markdown")
        
        # جلب الوصف
        ai_desc = get_ai_description(clean_name)

        # تنسيق المنشور
        caption = (
            f"📚 **العنوان:** {clean_name}\n\n"
            f"✨ **درر الوصف:**\n{ai_desc}\n\n"
            f"🇾🇪 **مكتبة اليمن الدولية**\n"
            f"🔗 {MAIN_CHANNEL}\n"
            f"ـــــــــــــــــــــــــــــــــــــــــــــــــــــ\n"
            f"📢 *ساهم في نشر العلم والمعرفة*"
        )

        # زر الانضمام للقناة
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("انضم للمكتبة 🏛️", url=f"https://t.me/{MAIN_CHANNEL.replace('@','')}")
        markup.add(btn)

        # 1. النشر في القناة (نسخ الرسالة للحفاظ على الملف الأصلي)
        bot.copy_message(
            chat_id=MAIN_CHANNEL,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=markup
        )

        # 2. الحفظ في قاعدة البيانات
        cur.execute("INSERT INTO books (name) VALUES (?)", (clean_name,))
        conn.commit()
        conn.close()

        # 3. تبشير المستخدم
        bot.edit_message_text(f"✅ **تم النشر بنجاح:** {clean_name}", message.chat.id, wait_msg.message_id, parse_mode="Markdown")
        logger.info(f"Published: {clean_name}")

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        try:
            bot.reply_to(message, f"❌ **عذراً:** حدث خطأ أثناء النشر.\nتأكد أن البوت (مشرف) في القناة.\nالخطأ: {e}")
        except:
            pass

# --- 5. التشغيل المستمر (Infinity Loop) ---
if __name__ == "__main__":
    print("🚀 نظام أمين (النسخة المتطورة) بدأ العمل في السحاب...")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"Connection Error: {e}")
            time.sleep(5) # انتظار 5 ثواني قبل إعادة المحاولة
            print("🔄 جاري إعادة الاتصال بالسيرفر...")
