import telebot
import sqlite3
import requests
import time
import os
import threading
from telebot import types
import html # مكتبة لتنظيف النصوص من الرموز المزعجة

# ==========================================
# ⚙️ الإعدادات الأساسية
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = "https://t.me/Yemen_International_Library"

bot = telebot.TeleBot(TOKEN)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'billion_lib.db')

# ==========================================
# 🗄️ تهيئة قاعدة البيانات
# ==========================================
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS files (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT)')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 محرك Gemini 1.5 Flash (تنسيق HTML)
# ==========================================
def get_ai_analysis(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    prompt = (
        f"حلل الكتاب: '{book_name}'. أعطني النتيجة فوراً بهذا التنسيق حصراً:\n"
        f"التصنيف | وصف مشوق في سطر | حكمة بليغة"
    )
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        ai_output = res['candidates'][0]['content']['parts'][0]['text']
        parts = ai_output.split('|')
        
        # تنظيف النصوص من أي رموز HTML قد يولدها الذكاء الاصطناعي بالخطأ
        res_data = {
            "cat": html.escape(parts[0].strip()) if len(parts) > 0 else "ثقافة",
            "desc": html.escape(parts[1].strip()) if len(parts) > 1 else "كتاب قيم.",
            "wisdom": html.escape(parts[2].strip()) if len(parts) > 2 else "العلم نور."
        }
        return res_data
    except:
        return {"cat": "منوعات", "desc": "كتاب قيم من مكتبتنا.", "wisdom": "اقرأ لترقى."}

# ==========================================
# 📥 استقبال وجدولة الملفات
# ==========================================
@bot.message_handler(content_types=['document', 'video', 'audio'])
def handle_queue(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        file_obj = message.document or message.video or message.audio
        file_name = getattr(file_obj, 'file_name', "كتاب_جديد")
        file_hash = f"{file_name}_{file_obj.file_size}"
        
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT OR IGNORE INTO files VALUES (?, ?, ?, ?)", (file_hash, file_name, file_obj.file_id, 'pending'))
        conn.commit()
        conn.close()
    except: pass

# ==========================================
# ⚙️ موظف النشر بنظام HTML (الحل الجذري)
# ==========================================
def publisher_worker():
    print("🚀 موظف النشر يعمل الآن بنظام HTML...")
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                clean_name = html.escape(f_name.replace('.pdf','').replace('_',' ').strip())
                
                ai = get_ai_analysis(clean_name)
                
                # بناء الرسالة باستخدام وسم HTML بدلاً من Markdown
                caption = (
                    f"📖 <b>{clean_name}</b>\n\n"
                    f"📂 <b>التصنيف:</b> {ai['cat']}\n"
                    f"📝 <b>عن الكتاب:</b> {ai['desc']}\n"
                    f"💎 <b>درر:</b> <i>{ai['wisdom']}</i>\n\n"
                    f"🔖 #{ai['cat'].replace(' ','_')} #مكتبة_المليار\n"
                    f"🏛️ <a href='{LIB_LINK}'>{LIB_NAME}</a>"
                )

                try:
                    # تم تغيير parse_mode إلى HTML
                    bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="HTML")
                    cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                    conn.commit()
                    print(f"✅ تم النشر بنجاح: {clean_name}")
                    time.sleep(15) 
                except Exception as post_err:
                    print(f"❌ خطأ نشر: {post_err}")
                    # في حال فشل HTML أيضاً (نادر جداً)، ننشر بدون تنسيق لضمان استمرار الطابور
                    try:
                        bot.send_document(MAIN_CHANNEL, f_id, caption=f"الكتاب: {clean_name}\nرابط المكتبة: {LIB_LINK}")
                        cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                        conn.commit()
                    except:
                        cur.execute("UPDATE files SET status='failed' WHERE hash=?", (f_hash,))
                        conn.commit()
            else:
                time.sleep(10)
            conn.close()
        except Exception as e:
            print(f"Worker Error: {e}")
            time.sleep(10)

# ==========================================
# 🕹️ الأوامر
# ==========================================
@bot.message_handler(commands=['admin', 'status'])
def send_report(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(db_path)
    p = conn.execute("SELECT COUNT(*) FROM files WHERE status='pending'").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM files WHERE status='published'").fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 <b>حالة المكتبة:</b>\n⏳ في الانتظار: {p}\n✅ تم النشر: {s}", parse_mode="HTML")

if __name__ == "__main__":
    threading.Thread(target=publisher_worker, daemon=True).start()
    bot.infinity_polling()
