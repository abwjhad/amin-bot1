import telebot
import sqlite3
import requests
import time
import os
import logging
import random
from telebot import types

# --- 1. الإعدادات والتوثيق ---
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
MAIN_CHANNEL = "@Yemen_International_Library" 
ADMIN_ID = 591617267  # ضع الآيدي الخاص بك هنا لتتمكن من استخدام أوامر الأدمن

# اسم المكتبة والشعار
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# --- 2. قاعدة البيانات ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'library.db')

def get_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS books (
            name TEXT PRIMARY KEY, 
            file_id TEXT,
            msg_id INTEGER,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn, cur

# --- 3. محرك الذكاء الاصطناعي (المطور) ---
def get_book_details(book_name):
    """
    يجلب التصنيف، الوصف، ودرر متنوعة (نصائح/حكم)
    """
    # قائمة مواضيع عشوائية لضمان عدم تكرار الكلام
    topics = [
        "محاربة الجهل وأهمية القراءة",
        "نصيحة للشباب لاستغلال الوقت في العلم",
        "قصص كفاح العلماء وصبرهم على القراءة",
        "تنمية العقل وبناء الوعي",
        "البدء في التعلم مهما كان العمر متأخراً",
        "أثر الكتاب في نهضة الشعوب الفقيرة",
        "الفرق بين العالم والجاهل"
    ]
    selected_topic = random.choice(topics)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
    # هندسة الأوامر للحصول على رد JSON أو هيكل منظم
    prompt = (
        f"الكتاب: '{book_name}'.\n"
        f"المطلوب منك 3 أشياء منفصلة بوضوح:\n"
        f"1. تصنيف الكتاب (كلمة أو كلمتين مثل: رواية، كتاب علمي، ديني...).\n"
        f"2. وصف مختصر للكتاب (سطرين).\n"
        f"3. فقرة 'درر' تتحدث عن ({selected_topic}) وتربطها بسياق هذا الكتاب بأسلوب ملهم وجذاب.\n"
        f"الرد يجب أن يكون بهذا التنسيق تماماً:\n"
        f"التصنيف: [اكتب التصنيف هنا]\n"
        f"الوصف: [اكتب الوصف هنا]\n"
        f"درر: [اكتب الفقرة هنا]"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        text = response.json()['candidates'][0]['content']['parts'][0]['text']
        return text
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return f"التصنيف: عام\nالوصف: كتاب قيم يضيف لعقلك الكثير.\nدرر: {selected_topic}."

# --- 4. أوامر الأدمن والبداية ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        f"أهلاً بك في بوت {LIB_NAME} 🤖\n\n"
        f"أنا أقوم بأرشفة الكتب تلقائياً مع وصف ذكي وتصنيف دقيق.\n"
        f"فقط أرسل الملف وسأقوم بالباقي!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['admin'])
def admin_stats(message):
    # أمر خاص بالأدمن فقط
    if message.from_user.id != ADMIN_ID:
        return
    
    conn, cur = get_db()
    cur.execute("SELECT COUNT(*) FROM books")
    count = cur.fetchone()[0]
    conn.close()
    
    bot.reply_to(message, f"📊 **إحصائيات المكتبة:**\nعدد الكتب المؤرشفة: {count}")

# --- 5. معالجة الملفات (المخ) ---
@bot.message_handler(content_types=['document', 'audio', 'video'])
def handle_docs(message):
    try:
        # 1. استخراج الاسم
        if message.document:
            file_name = message.document.file_name
            file_size = message.document.file_size
        elif message.audio:
            file_name = f"{message.audio.title} - {message.audio.performer}"
            file_size = message.audio.file_size
        elif message.video:
            file_name = message.caption if message.caption else "فيديو تعليمي"
            file_size = message.video.file_size
        else:
            return

        # حساب الحجم بالميجابايت
        size_mb = f"{file_size / (1024 * 1024):.2f} MB"
        
        # تنظيف الاسم
        clean_name = str(file_name).replace('.pdf', '').replace('.epub', '').replace('_', ' ').strip()
        
        # 2. فحص التكرار
        conn, cur = get_db()
        cur.execute("SELECT name FROM books WHERE name=?", (clean_name,))
        if cur.fetchone():
            bot.reply_to(message, f"⚠️ الكتاب '{clean_name}' موجود مسبقاً!")
            conn.close()
            return

        # رسالة انتظار
        status_msg = bot.reply_to(message, "⏳ **جاري تحليل الكتاب، التصنيف، وكتابة الدرر...**", parse_mode="Markdown")
        
        # 3. جلب بيانات الذكاء الاصطناعي
        ai_response = get_book_details(clean_name)
        
        # محاولة فصل البيانات (التصنيف، الوصف، الدرر)
        category = "عام"
        description = "وصف غير متاح"
        durar = "العلم نور."
        
        for line in ai_response.split('\n'):
            if "التصنيف:" in line: category = line.replace("التصنيف:", "").strip()
            elif "الوصف:" in line: description = line.replace("الوصف:", "").strip()
            elif "درر:" in line: durar = line.replace("درر:", "").strip()
            # التقاط باقي سطور الدرر إذا كانت طويلة
            elif len(line) > 10 and "التصنيف" not in line and "الوصف" not in line:
                durar += f"\n{line}"

        # 4. تنسيق الرسالة النهائي (كما طلبت)
        caption = (
            f"📖 **اسم الكتاب:** {clean_name}\n"
            f"🏷️ **التصنيف:** {category}\n"
            f"📝 **وصف الكتاب:**\n{description}\n\n"
            f"💾 **حجم الكتاب:** {size_mb}\n\n"
            f"💎 **درر:**\n{durar}\n\n"
            f"🏛️ **[{LIB_NAME}]({LIB_LINK})**\n"
            f"💠 (كتب علمية، روايات، ثقافة، دين، خرافات)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📢 *ساهم في نشر العلم والمعرفة*\n\n"
            f"🔍 **كيفية البحث:** اضغط على اسم القناة 👈 ثم بحث 🔍 واكتب اسم الكتاب."
        )

        # 5. النشر
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(f"انضم لـ {LIB_NAME}", url=LIB_LINK)
        markup.add(btn)

        bot.copy_message(MAIN_CHANNEL, message.chat.id, message.message_id, caption=caption, parse_mode="Markdown", reply_markup=markup)
        
        # الحفظ
        cur.execute("INSERT INTO books (name, file_id, msg_id) VALUES (?, ?, ?)", (clean_name, message.document.file_id if message.document else "N/A", message.id))
        conn.commit()
        conn.close()

        bot.edit_message_text(f"✅ تم النشر: {clean_name}", message.chat.id, status_msg.message_id)
        logger.info(f"Published: {clean_name}")

    except Exception as e:
        logger.error(f"Error: {e}")
        try:
            bot.edit_message_text(f"❌ خطأ: {e}", message.chat.id, status_msg.message_id)
        except:
            pass
        
    time.sleep(random.randint(4, 8))

# --- التشغيل ---
if __name__ == "__main__":
    print("🚀 مكتبة المليار كتاب تعمل الآن...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            logger.error(f"Restarting... Error: {e}")
            time.sleep(5)
