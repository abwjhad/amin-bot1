import telebot
import sqlite3
import requests
import time
import os
import threading
import logging
from telebot import types
from datetime import datetime

# ==========================================
# ⚙️ الإعدادات (تأكد من صحتها)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/Yemen_International_Library"

# سرعة النشر: 15 ثانية (توازن مثالي بين السرعة والأمان)
POST_DELAY = 15 

bot = telebot.TeleBot(TOKEN)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'billion_lib.db')

# ==========================================
# 🗄️ نظام قاعدة البيانات (محمي من التعليق)
# ==========================================
def init_db():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 محرك Gemini 1.5 Flash (الأسرع عالمياً)
# ==========================================
def get_ai_analysis(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    prompt = (
        f"حلل الكتاب: '{book_name}'. أعطني النتيجة فوراً بهذا التنسيق حصراً:\n"
        f"التصنيف | وصف مشوق في سطر | حكمة بليغة تناسب المحتوى"
    )
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        ai_output = res['candidates'][0]['content']['parts'][0]['text']
        parts = ai_output.split('|')
        return {
            "cat": parts[0].strip() if len(parts) > 0 else "ثقافة عامة",
            "desc": parts[1].strip() if len(parts) > 1 else "من كنوز المعرفة الأصيلة.",
            "wisdom": parts[2].strip() if len(parts) > 2 else "خير جليس في الزمان كتاب."
        }
    except Exception as e:
        print(f"AI Error: {e}")
        return {"cat": "منوعات", "desc": "كتاب قيم جداً.", "wisdom": "القراءة تفتح آفاق العقل."}

# ==========================================
# 📥 استقبال الملفات (جدولة فورية)
# ==========================================
@bot.message_handler(content_types=['document', 'video', 'audio'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        file_obj = message.document or message.video or message.audio
        file_name = getattr(file_obj, 'file_name', "كتاب_غير_معرف")
        file_hash = f"{file_name}_{file_obj.file_size}"
        
        conn = sqlite3.connect(db_path, timeout=20)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO files VALUES (?, ?, ?, ?)", (file_hash, file_name, file_obj.file_id, 'pending'))
        conn.commit()
        conn.close()
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ خطأ أثناء الاستلام: {e}")

# ==========================================
# ⚙️ موظف النشر (الذي يعمل الآن بصمت وقوة)
# ==========================================
def publisher_worker():
    print("🚀 انطلاق موظف النشر الذكي...")
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            
            # جلب أول كتاب في الانتظار
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                clean_name = f_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
                
                # تحليل الفلاش السريع
                ai = get_ai_analysis(clean_name)
                
                caption = (
                    f"📖 **{clean_name}**\n\n"
                    f"📂 **التصنيف:** {ai['cat']}\n"
                    f"📝 **عن الكتاب:** {ai['desc']}\n"
                    f"💎 **درر:** _{ai['wisdom']}_\n\n"
                    f"🔖 #{ai['cat'].replace(' ','_')} #مكتبة_المليار\n"
                    f"🏛️ **[{LIB_NAME}]({LIB_LINK})**"
                )

                try:
                    bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="Markdown")
                    # تحديث الحالة لمنشور
                    cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                    conn.commit()
                    print(f"✅ تم نشر: {clean_name}")
                    time.sleep(POST_DELAY)
                except Exception as post_err:
                    error_str = str(post_err)
                    if "429" in error_str: # حماية من حظر تليجرام
                        time.sleep(60)
                    else:
                        bot.send_message(ADMIN_ID, f"🚨 فشل النشر للقناة!\nالكتاب: {f_name}\nالخطأ: {error_str}")
                        cur.execute("UPDATE files SET status='failed' WHERE hash=?", (f_hash,))
                        conn.commit()
            else:
                time.sleep(10) # الطابور فارغ، انتظر قليلاً
            
            conn.close()
        except Exception as global_e:
            print(f"Worker Error: {global_e}")
            time.sleep(10)

# ==========================================
# 🕹️ أوامر الإدارة
# ==========================================
@bot.message_handler(commands=['admin', 'status', 'start'])
def send_status(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        p = cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'").fetchone()[0]
        s = cur.execute("SELECT COUNT(*) FROM files WHERE status='published'").fetchone()[0]
        conn.close()
        
        msg = (
            f"📊 **حالة مكتبة المليار:**\n\n"
            f"⏳ في الانتظار: {p}\n"
            f"✅ تم النشر: {s}\n"
            f"🚀 المحرك: Gemini 1.5 Flash\n"
            f"⚙️ الحالة: متصل ويعمل"
        )
        bot.reply_to(message, msg, parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ قاعدة البيانات قيد التحديث، حاول مجدداً.")

# ==========================================
# 🔥 التشغيل الفعلي
# ==========================================
if __name__ == "__main__":
    # تشغيل محرك النشر في خيط منفصل لضمان عدم توقف الاستقبال
    threading.Thread(target=publisher_worker, daemon=True).start()
    
    print("🤖 البوت متصل الآن ومستعد للمليار كتاب...")
    bot.infinity_polling()
