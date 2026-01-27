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
# ⚙️ الإعدادات الأساسية
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

# الفاصل الزمني للنشر (15 ثانية آمن جداً ومناسب للسرعة)
POST_DELAY = 15 

bot = telebot.TeleBot(TOKEN)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'billion_lib.db')

# ==========================================
# 🗄️ تهيئة قاعدة البيانات
# ==========================================
def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT, date_added TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('maintenance', 'OFF')")
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 محرك الذكاء الاصطناعي (Gemini 1.5 Flash السريع)
# ==========================================
def get_ai_analysis(book_name):
    """استخدام موديل Flash للتحليل السريع والدقيق"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (
        f"أنت خبير مكتبات. حلل عنوان الكتاب: '{book_name}'.\n"
        f"المطلوب استخراج البيانات التالية بدقة وبلاغة:\n"
        f"1. التصنيف: اختر بدقة من (سياسي، ديني، علمي، ثقافي، توعية، رواية، تاريخ، تقنية).\n"
        f"2. نبذة: وصف بليغ وجذاب في سطرين.\n"
        f"3. درر: اختر حكمة عالمية أو مقولة عربية أو سجعاً يمنياً بليغاً يناسب محتوى الكتاب.\n\n"
        f"نسق الإجابة هكذا (مهم جداً الفصل بعلامة |):\n"
        f"التصنيف | النبذة | الدرر"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=10).json()
        ai_output = res['candidates'][0]['content']['parts'][0]['text']
        parts = ai_output.split('|')
        return {
            "cat": parts[0].strip() if len(parts) > 0 else "ثقافة",
            "desc": parts[1].strip() if len(parts) > 1 else "كتاب قيم ضمن مكتبتنا.",
            "durar": parts[2].strip() if len(parts) > 2 else "العلم يرفع بيتاً لا عماد له."
        }
    except Exception as e:
        print(f"AI Error: {e}")
        return {"cat": "ثقافة", "desc": "كتاب قيم من كنوز المعرفة.", "durar": "اقرأ لترقى."}

# ==========================================
# 📥 استقبال الملفات والجدولة
# ==========================================
@bot.message_handler(content_types=['document', 'video', 'audio'])
def handle_incoming_queue(message):
    if message.from_user.id != ADMIN_ID: return
    
    try:
        file_obj = message.document or message.video or message.audio
        file_name = file_obj.file_name if hasattr(file_obj, 'file_name') else "كتاب_جديد"
        file_hash = f"{file_name}_{file_obj.file_size}"
        
        conn = sqlite3.connect(db_path, timeout=20)
        cur = conn.cursor()
        
        # منع التكرار
        cur.execute("SELECT status FROM files WHERE hash=?", (file_hash,))
        if cur.fetchone():
            return # يتجاهل المكرر بصمت لمنع الإزعاج أثناء تحويل 1000 كتاب

        # الإضافة للطابور
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?, ?)", 
                    (file_hash, file_name, file_obj.file_id, 'pending', datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Queue Error: {e}")

# ==========================================
# ⚙️ موظف النشر الخلفي (The Flash Worker)
# ==========================================

def publisher_worker():
    print("🚀 موظف النشر السريع (Gemini Flash) انطلق...")
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            
            # جلب أول كتاب ينتظر
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' ORDER BY rowid ASC LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                clean_name = f_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
                
                # تحليل ذكي سريع
                ai = get_ai_analysis(clean_name)
                
                # تنسيق المنشور النهائي
                caption = (
                    f"📖 **اسم الكتاب:** {clean_name}\n"
                    f"🏷️ **التصنيف:** {ai['cat']}\n"
                    f"📝 **وصف الكتاب:** {ai['desc']}\n\n"
                    f"💾 **الحجم:** (يتم المعالجة)\n\n" # تليجرام يظهر الحجم تلقائياً في الملفات
                    f"💎 **درر:** {ai['durar']}\n\n"
                    f"🏛️ **[{LIB_NAME}]({LIB_LINK})**\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📢 ساهم في نشر العلم والمعرفة\n"
                    f"#{ai['cat'].replace(' ','_')} #مكتبة_المليار"
                )

                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton("انضم للمكتبة 📚", url=LIB_LINK))
                
                try:
                    bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
                    cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                    conn.commit()
                    print(f"✅ تم نشر: {clean_name}")
                    time.sleep(POST_DELAY) # استراحة آمنة
                except Exception as e:
                    if "429" in str(e):
                        wait = int(str(e).split("retry after ")[1])
                        time.sleep(wait + 5)
                    else:
                        cur.execute("UPDATE files SET status='failed' WHERE hash=?", (f_hash,))
                        conn.commit()
            else:
                time.sleep(10) # الطابور فارغ
            
            conn.close()
        except Exception as ge:
            print(f"Worker Error: {ge}")
            time.sleep(10)

# ==========================================
# 🕹️ لوحة تحكم الأدمن (الأوامر)
# ==========================================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
    p = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM files WHERE status='published'")
    s = cur.fetchone()[0]
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"⏳ الانتظار: {p}", callback_data="none"),
               types.InlineKeyboardButton(f"✅ المنشور: {s}", callback_data="none"))
    
    bot.send_message(message.chat.id, "🕹️ **لوحة التحكم - مكتبة المليار**\n\nالنظام يعمل بمحرك Gemini 1.5 Flash.", reply_markup=markup, parse_mode="Markdown")
    conn.close()

# ==========================================
# 🔥 انطلاق النظام
# ==========================================
if __name__ == "__main__":
    # تشغيل خيط النشر في الخلفية
    threading.Thread(target=publisher_worker, daemon=True).start()
    
    print("🤖 البوت يعمل ومستعد لاستقبال الـ 1000 كتاب...")
    bot.infinity_polling()
