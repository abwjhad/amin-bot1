import telebot
import sqlite3
import requests
import time
import os
import logging
import threading
from telebot import types
from datetime import datetime

# --- 1. إعدادات البوت والأدمن ---
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307  # الآيدي الخاص بك
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

# الفاصل الزمني بين كل منشور وآخر (بالثواني) لتجنب الحظر
POST_DELAY = 45 

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN)

# --- 2. قاعدة البيانات (طابور النشر) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'billion_lib.db')

def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    # جدول الملفات (تم إضافة status للطابور)
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, msg_id INTEGER, chat_id INTEGER, status TEXT, date_added TEXT)''')
    conn.commit()
    return conn

db_conn = init_db()

# --- 3. المخ (الذكاء الاصطناعي - تصنيف دقيق) ---
def get_ai_analysis(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
    # هندسة الأوامر للحصول على تصنيف دقيق
    prompt = (
        f"أنت خبير في تصنيف الكتب في مكتبة عالمية. الكتاب بعنوان: '{book_name}'.\n"
        f"قم بتحليله واستخرج البيانات التالية بدقة متناهية:\n"
        f"1. العنوان الرسمي: (اكتب العنوان بشكل صحيح بدون زيادات).\n"
        f"2. التصنيف: اختر واحداً فقط من (سياسة، دين، علوم، ثقافة، توعية، رواية، تاريخ، فلسفة، تقنية).\n"
        f"3. الوصف: وصف عميق ومختصر جداً في سطرين.\n"
        f"4. درر: اقتباس أو حكمة بليغة تناسب موضوع الكتاب تماماً (وليس حكمة عامة).\n"
        f"نسق الإجابة هكذا تماماً:\n"
        f"العنوان: [النص]\nالتصنيف: [النص]\nالوصف: [النص]\nدرر: [النص]"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20).json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except:
        return f"العنوان: {book_name}\nالتصنيف: عام\nالوصف: كتاب مميز ضمن مكتبة المليار.\nدرر: خير جليس في الزمان كتاب."

# --- 4. معالجة الملفات (الإضافة للطابور) ---
@bot.message_handler(content_types=['document', 'video', 'audio'])
def queue_files(message):
    try:
        # استخراج البيانات
        file_obj = message.document or message.video or message.audio
        file_name = file_obj.file_name if hasattr(file_obj, 'file_name') else message.caption or "كتاب"
        file_id = file_obj.file_id
        file_size = file_obj.file_size
        file_hash = f"{file_name}_{file_size}" # بصمة لمنع التكرار

        cur = db_conn.cursor()
        
        # 1. فحص التكرار (هل نُشر من قبل؟)
        cur.execute("SELECT status FROM files WHERE hash=?", (file_hash,))
        exists = cur.fetchone()
        if exists:
            if exists[0] == 'published':
                bot.reply_to(message, "⚠️ هذا الكتاب موجود بالفعل في القناة!")
            else:
                bot.reply_to(message, "⏳ هذا الكتاب موجود في الطابور وسينشر قريباً.")
            return

        # 2. الإضافة للطابور (Pending)
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)", 
                    (file_hash, file_name, file_id, message.message_id, message.chat.id, 'pending', datetime.now().strftime("%Y-%m-%d")))
        db_conn.commit()

        # حساب ترتيبه في الطابور
        cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
        queue_pos = cur.fetchone()[0]
        
        bot.reply_to(message, f"✅ **تمت الجدولة!**\nترتيبه في الطابور: {queue_pos}\nسيتم نشره تلقائياً دون تدخلك.")

    except Exception as e:
        logger.error(f"Queue Error: {e}")

# --- 5. نظام النشر التلقائي (Background Worker) ---
def publisher_worker():
    """وظيفة تعمل في الخلفية لمعالجة الطابور واحداً تلو الآخر"""
    print("⚙️ نظام جدولة النشر بدأ العمل...")
    while True:
        try:
            # جلب أقدم كتاب في الانتظار
            conn = sqlite3.connect(db_path) # اتصال خاص بالخيط
            cur = conn.cursor()
            cur.execute("SELECT hash, name, file_id, msg_id, chat_id FROM files WHERE status='pending' ORDER BY rowid ASC LIMIT 1")
            book = cur.fetchone()
            
            if book:
                f_hash, f_name, f_id, f_msg_id, f_chat_id = book
                
                # 1. تحليل الذكاء الاصطناعي
                clean_name = f_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
                ai_text = get_ai_analysis(clean_name)
                
                # تفكيك النص
                title, cat, desc, durar = clean_name, "عام", "وصف متاح", "العلم نور"
                for line in ai_text.split('\n'):
                    if "العنوان:" in line: title = line.replace("العنوان:", "").strip()
                    if "التصنيف:" in line: cat = line.replace("التصنيف:", "").strip()
                    if "الوصف:" in line: desc = line.replace("الوصف:", "").strip()
                    if "درر:" in line: durar = line.replace("درر:", "").strip()

                # تحديد الهاشتاجات بناءً على التصنيف
                hashtags = f"#{cat.replace(' ','_')} #كتب #مكتبة_المليار #اليمن"

                # 2. تنسيق الرسالة الاحترافية
                caption = (
                    f"📚 **العنوان:** {title}\n"
                    f"📂 **التصنيف:** {cat}\n\n"
                    f"📝 **نبذة:**\n{desc}\n\n"
                    f"💎 **درر:**\nProcessing...\n_{durar}_\n\n"
                    f"🔖 {hashtags}\n"
                    f"🏛️ **[{LIB_NAME}]({LIB_LINK})**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📢 *مشروع نشر مليار كتاب*"
                )

                # 3. النشر في القناة
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("انضم للمكتبة 📥", url=LIB_LINK))
                
                # إرسال الملف للقناة (نستخدم send_document بدلاً من copy لتفادي مشاكل الحذف)
                bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                
                # 4. تحديث الحالة إلى منشور
                cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                conn.commit()
                print(f"🚀 تم نشر: {title}")
                
                # 5. فترة راحة لتجنب الحظر (45 ثانية)
                time.sleep(POST_DELAY)
            
            else:
                # إذا الطابور فارغ، انتظر قليلاً ثم افحص مرة أخرى
                time.sleep(5)
            
            conn.close()

        except Exception as e:
            print(f"Publisher Error: {e}")
            time.sleep(10) # انتظار عند الخطأ

# --- 6. أوامر التحكم (Admin) ---
@bot.message_handler(commands=['queue'])
def check_queue(message):
    if message.from_user.id != ADMIN_ID: return
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
    count = cur.fetchone()[0]
    bot.reply_to(message, f"📊 **حالة الطابور:**\nيوجد {count} كتاب قيد الانتظار للنشر.")

# --- التشغيل ---
if __name__ == "__main__":
    # تشغيل خيط النشر في الخلفية
    threading.Thread(target=publisher_worker, daemon=True).start()
    
    print("🤖 البوت يعمل ويستقبل الملفات...")
    bot.infinity_polling()
