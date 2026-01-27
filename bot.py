import telebot
import sqlite3
import requests
import time
import os
import threading
from telebot import types
from datetime import datetime

# --- إعداداتك ---
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

# توقيت النشر: 15 ثانية (آمن جداً لـ 1000 كتاب)
POST_DELAY = 15 

bot = telebot.TeleBot(TOKEN)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'billion_lib.db')

# --- تهيئة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- ذكاء اصطناعي فلاش (التصنيف الدقيق) ---
def get_ai_flash(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    prompt = (
        f"حلل بدقة الكتاب: '{book_name}'.\n"
        f"أعطني النتيجة بتنسيق واحد فقط كالتالي:\n"
        f"التصنيف (سياسي أو ديني أو علمي أو ثقافي أو توعية) | وصف سطر واحد | حكمة بليغة"
    )
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        raw = res['candidates'][0]['content']['parts'][0]['text']
        parts = raw.split('|')
        return {
            "cat": parts[0].strip() if len(parts)>0 else "ثقافي",
            "desc": parts[1].strip() if len(parts)>1 else "كتاب مميز وقيم.",
            "durar": parts[2].strip() if len(parts)>2 else "العلم نور."
        }
    except:
        return {"cat": "ثقافي", "desc": "كتاب قيم.", "durar": "اقرأ لترقى."}

# --- استقبال الملفات (الجدولة) ---
@bot.message_handler(content_types=['document', 'video', 'audio'])
def queue_books(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        file_obj = message.document or message.video or message.audio
        file_name = getattr(file_obj, 'file_name', "كتاب_جديد")
        file_hash = f"{file_name}_{file_obj.file_size}"
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO files VALUES (?, ?, ?, ?)", (file_hash, file_name, file_obj.file_id, 'pending'))
        conn.commit()
        conn.close()
    except: pass

# --- موظف النشر (Scheduler) ---
def publisher():
    while True:
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                clean_name = f_name.replace('.pdf','').replace('_',' ')
                
                # استدعاء الذكاء الاصطناعي
                ai = get_ai_flash(clean_name)
                
                caption = (
                    f"📖 **{clean_name}**\n\n"
                    f"🏷️ **التصنيف:** {ai['cat']}\n"
                    f"📝 **عن الكتاب:** {ai['desc']}\n"
                    f"💎 **درر:** _{ai['durar']}_\n\n"
                    f"🔖 #{ai['cat']} #مكتبة_المليار\n"
                    f"🏛️ **[{LIB_NAME}]({LIB_LINK})**"
                )

                bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="Markdown")
                cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                conn.commit()
                time.sleep(POST_DELAY)
            else:
                time.sleep(10)
            conn.close()
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# --- أوامر التحكم ---
@bot.message_handler(commands=['admin'])
def status(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    p = cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'").fetchone()[0]
    s = cur.execute("SELECT COUNT(*) FROM files WHERE status='published'").fetchone()[0]
    bot.reply_to(message, f"📊 **لوحة التحكم**\n\n⏳ الانتظار: {p}\n✅ المنشور: {s}\n🤖 المحرك: Gemini 1.5 Flash")
    conn.close()

if __name__ == "__main__":
    threading.Thread(target=publisher, daemon=True).start()
    bot.infinity_polling()
