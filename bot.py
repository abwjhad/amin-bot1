import telebot
import sqlite3
import requests
import time
import os
import logging
import threading
from telebot import types
from datetime import datetime

# ==========================================
# ⚙️ إعدادات البوت (تعديلك هنا فقط)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library" # تأكد أن البوت مشرف هنا
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

# سرعة النشر (بالثواني) - جعلناها 15 ثانية لتسريع الطابور بأمان
POST_DELAY = 15 

# ==========================================
# 🗄️ نظام قاعدة البيانات (المعدل)
# ==========================================
bot = telebot.TeleBot(TOKEN)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'billion_lib.db')

def init_db():
    """إنشاء الجداول عند التشغيل لأول مرة"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    # جدول الملفات مع عمود الحالة (status)
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, msg_id INTEGER, chat_id INTEGER, status TEXT, date_added TEXT)''')
    conn.commit()
    conn.close()

# تهيئة القاعدة عند البدء
init_db()

# ==========================================
# 🧠 الذكاء الاصطناعي (Gemini)
# ==========================================
def get_ai_analysis(book_name):
    """تحليل الكتاب وتصنيفه"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
    prompt = (
        f"الكتاب بعنوان: '{book_name}'.\n"
        f"قم بتحليله واستخرج التالي بدقة:\n"
        f"1. العنوان الصافي.\n"
        f"2. التصنيف (سياسة، دين، رواية، تاريخ، تقنية، فلسفة، علوم، تطوير ذات).\n"
        f"3. وصف مختصر جداً وجذاب في سطرين.\n"
        f"4. حكمة أو مقولة بليغة (درر) تناسب الموضوع.\n"
        f"نسق الإجابة هكذا:\n"
        f"العنوان: [النص]\nالتصنيف: [النص]\nالوصف: [النص]\nدرر: [النص]"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"AI Error: {e}")
        return None # في حال الفشل نعود لـ None

# ==========================================
# 📥 استقبال الملفات (Main Thread)
# ==========================================
@bot.message_handler(content_types=['document', 'video', 'audio'])
def receive_files(message):
    try:
        # 1. التحقق من الأدمن
        if message.from_user.id != ADMIN_ID:
            return # تجاهل رسائل الغرباء

        file_obj = message.document or message.video or message.audio
        file_name = file_obj.file_name if hasattr(file_obj, 'file_name') else "كتاب_مجهول"
        file_id = file_obj.file_id
        file_size = file_obj.file_size
        file_hash = f"{file_name}_{file_size}"

        # اتصال مؤقت وسريع بالقاعدة للإضافة
        conn = sqlite3.connect(db_path, timeout=10)
        cur = conn.cursor()

        # هل الكتاب موجود؟
        cur.execute("SELECT status FROM files WHERE hash=?", (file_hash,))
        exists = cur.fetchone()
        
        if exists:
            if exists[0] == 'published':
                bot.reply_to(message, "⚠️ منشور سابقاً!")
            elif exists[0] == 'pending':
                bot.reply_to(message, "⏳ موجود في الطابور!")
        else:
            # إضافة جديد
            cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)", 
                        (file_hash, file_name, file_id, message.message_id, message.chat.id, 'pending', datetime.now().strftime("%Y-%m-%d")))
            conn.commit()
            
            # إعلام الأدمن بترتيب الطابور كل 50 كتاب (لتقليل الإزعاج)
            cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
            count = cur.fetchone()[0]
            if count % 10 == 1: # تنبيه عند الكتاب 1، 11، 21...
                bot.reply_to(message, f"✅ تمت الجدولة. في الانتظار: {count}")
        
        conn.close()

    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الاستلام: {e}")

# ==========================================
# ⚙️ موظف النشر الخلفي (The Worker)
# ==========================================
def publisher_worker():
    """يعمل في الخلفية لنشر الكتب واحداً تلو الآخر"""
    print("🚀 بدء تشغيل موظف النشر...")
    time.sleep(5) # انتظار إقلاع النظام
    
    while True:
        try:
            # 1. فتح اتصال خاص (مهم جداً لمنع التداخل)
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            
            # 2. البحث عن أقدم كتاب معلق (Pending)
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' ORDER BY rowid ASC LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                print(f"🔄 جاري معالجة: {f_name}")
                
                # --- مرحلة التجهيز (AI) ---
                clean_name = f_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
                ai_result = get_ai_analysis(clean_name)
                
                # قيم افتراضية
                title = clean_name
                cat = "كتب عامة"
                desc = "كتاب قيم يستحق القراءة."
                durar = "العلم يبني بيوتاً لا عماد لها."
                
                # استخراج بيانات AI إن وجدت
                if ai_result:
                    for line in ai_result.split('\n'):
                        if "العنوان:" in line: title = line.replace("العنوان:", "").strip()
                        if "التصنيف:" in line: cat = line.replace("التصنيف:", "").strip()
                        if "الوصف:" in line: desc = line.replace("الوصف:", "").strip()
                        if "درر:" in line: durar = line.replace("درر:", "").strip()
                
                # هاشتاجات
                hashtags = f"#{cat.replace(' ','_')} #مكتبة_المليار #كتب"

                # تنسيق الرسالة
                caption = (
                    f"📚 **{title}**\n\n"
                    f"📂 **التصنيف:** {cat}\n"
                    f"📝 **نبذة:**\n{desc}\n\n"
                    f"💎 **درر:**\n_{durar}_\n\n"
                    f"🔖 {hashtags}\n"
                    f"🏛️ **[{LIB_NAME}]({LIB_LINK})**"
                )

                # --- مرحلة النشر ---
                try:
                    kb = types.InlineKeyboardMarkup()
                    kb.add(types.InlineKeyboardButton("تابع القناة الرسمية 📚", url=LIB_LINK))
                    
                    bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                    
                    # نجاح النشر
                    cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                    conn.commit()
                    print(f"✅ تم النشر: {title}")
                    
                    # وقت الراحة (15 ثانية)
                    time.sleep(POST_DELAY)
                    
                except telebot.apihelper.ApiTelegramException as e:
                    # معالجة أخطاء تليجرام بذكاء
                    if e.error_code == 429: # Too Many Requests
                        retry_time = e.result_json['parameters']['retry_after']
                        print(f"⚠️ انتظار إجباري من تليجرام: {retry_time} ثانية")
                        bot.send_message(ADMIN_ID, f"⚠️ تليجرام طلب هدنة {retry_time} ثانية.. سأنتظر.")
                        time.sleep(retry_time + 5)
                    else:
                        # خطأ آخر (مثل الصلاحيات)
                        print(f"❌ فشل النشر: {e}")
                        cur.execute("UPDATE files SET status='failed' WHERE hash=?", (f_hash,))
                        conn.commit()
                        bot.send_message(ADMIN_ID, f"🚨 فشل نشر كتاب: {clean_name}\nالسبب: {e}")

            else:
                # لا توجد كتب في الطابور
                time.sleep(10)

            conn.close() # إغلاق الاتصال في كل دورة
            
        except Exception as global_e:
            print(f"⚠️ خطأ عام في الموظف: {global_e}")
            time.sleep(10)

# ==========================================
# 🎮 أوامر التحكم (Admin)
# ==========================================
@bot.message_handler(commands=['status', 'بدء'])
def system_status(message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM files WHERE status='published'")
    published = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM files WHERE status='failed'")
    failed = cur.fetchone()[0]
    conn.close()
    
    msg = (
        f"📊 **تقرير الحالة:**\n"
        f"⏳ قيد الانتظار: {pending}\n"
        f"✅ تم النشر: {published}\n"
        f"❌ فشل النشر: {failed}\n"
        f"⚙️ الحالة: النظام يعمل."
    )
    bot.reply_to(message, msg, parse_mode="Markdown")

# ==========================================
# 🔥 التشغيل
# ==========================================
if __name__ == "__main__":
    # تشغيل خيط النشر في الخلفية
    worker_thread = threading.Thread(target=publisher_worker, daemon=True)
    worker_thread.start()
    
    print("✅ البوت قيد العمل... (Worker started)")
    bot.infinity_polling()
