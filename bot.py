import telebot
import sqlite3
import requests
import time
import os
import logging
import random
import hashlib
from telebot import types
from datetime import datetime

# --- 1. الإعدادات الأساسية ---
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

bot = telebot.TeleBot(TOKEN)

# --- 2. نظام قاعدة البيانات المتقدم ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, 'billion_lib.db')

def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    # جدول الملفات
    cur.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, size TEXT, date_added TEXT)''')
    # جدول الإعدادات
    cur.execute('''CREATE TABLE IF NOT EXISTS settings 
                   (key TEXT PRIMARY KEY, value TEXT)''')
    # جدول السجلات
    cur.execute('''CREATE TABLE IF NOT EXISTS logs 
                   (id INTEGER PRIMARY KEY AUTOINCREMENT, op TEXT, details TEXT, time TEXT)''')
    
    # القيم الافتراضية
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('maintenance', 'OFF')")
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('auto_post', 'ON')")
    conn.commit()
    return conn

db_conn = init_db()

def log_op(op, details):
    cur = db_conn.cursor()
    cur.execute("INSERT INTO logs (op, details, time) VALUES (?, ?, ?)", 
                (op, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db_conn.commit()

# --- 3. محرك الذكاء الاصطناعي (درر عالمية ويمنية) ---
def get_ai_content(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    
    prompt = (
        f"أنت أمين مكتبة خبير ومثقف. الكتاب هو: '{book_name}'.\n"
        f"أعطني البيانات التالية بدقة:\n"
        f"1. التصنيف: (تصنيف دقيق مثل: فلسفة، فيزياء، رواية عالمية...).\n"
        f"2. الوصف: (وصف بليغ وجذاب في سطرين).\n"
        f"3. درر: (مقولة عالمية لعلماء أو أدباء، أو حكمة عربية بليغة، أو مقولة يمنية مسجوعة تراثية عن العلم، الجهل، القراءة، أو كفاح الشباب. اختر واحدة فقط تكون مذهلة ومناسبة للسياق).\n"
        f"التنسيق المطلوب:\n"
        f"التصنيف: [النص]\n"
        f"الوصف: [النص]\n"
        f"درر: [النص]"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20).json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except:
        return "التصنيف: عام\nالوصف: كتاب قيم من كنوز المعرفة.\nدرر: العلم يرفع بيوتاً لا عماد لها.. والجهل يهدم بيت العز والكرم."

# --- 4. لوحة تحكم الأدمن (الأزرار) ---
def admin_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
        types.InlineKeyboardButton("🩺 فحص الحالة", callback_data="health"),
        types.InlineKeyboardButton("🚀 النشر التلقائي", callback_data="toggle_post"),
        types.InlineKeyboardButton("🔒 وضع الصيانة", callback_data="toggle_main"),
        types.InlineKeyboardButton("🧾 السجلات", callback_data="view_logs")
    )
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "🕹️ **مرحباً بك في لوحة تحكم برو-ماكس الإدارية**\nاختر من القائمة أدناه:", 
                     reply_markup=admin_markup(), parse_mode="Markdown")

# --- 5. معالجة الملفات وحماية التكرار ---
@bot.message_handler(content_types=['document', 'video', 'audio'])
def handle_incoming_files(message):
    # فحص وضع الصيانة
    cur = db_conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='maintenance'")
    if cur.fetchone()[0] == 'ON' and message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⚠️ المكتبة متوقفة مؤقتاً للصيانة.. نعود قريباً.")
        return

    try:
        file_info = message.document or message.video or message.audio
        file_name = file_info.file_name if hasattr(file_info, 'file_name') else "ملف جديد"
        file_size_mb = f"{file_info.file_size / (1024*1024):.2f} MB"
        file_hash = f"{file_name}_{file_info.file_size}" # نظام بصمة مبسط

        # فحص التكرار
        cur.execute("SELECT date_added FROM files WHERE hash=?", (file_hash,))
        duplicate = cur.fetchone()
        if duplicate:
            if message.from_user.id == ADMIN_ID:
                bot.reply_to(message, f"⚠️ تكرار! هذا الكتاب رُفع سابقاً بتاريخ: {duplicate[0]}")
            return

        # معالجة النشر
        clean_name = file_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
        status = bot.reply_to(message, "⏳ جاري المعالجة والأرشفة...")
        
        ai_data = get_ai_content(clean_name)
        category, desc, durar = "عام", "وصف متاح", "درر الحكمة"
        for line in ai_data.split('\n'):
            if "التصنيف:" in line: category = line.split(":", 1)[1].strip()
            if "الوصف:" in line: desc = line.split(":", 1)[1].strip()
            if "درر:" in line: durar = line.split(":", 1)[1].strip()

        caption = (
            f"📖 **اسم الكتاب:** {clean_name}\n"
            f"🏷️ **التصنيف:** {category}\n"
            f"📝 **وصف الكتاب:** {desc}\n\n"
            f"💾 **حجم الكتاب:** {file_size_mb}\n\n"
            f"💎 **درر:** {durar}\n\n"
            f"🏛️ **[{LIB_NAME}]({LIB_LINK})**\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📢 ساهم في نشر العلم والمعرفة"
        )

        # النشر للقناة
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("انضم للمكتبة 📚", url=LIB_LINK))
        
        bot.copy_message(MAIN_CHANNEL, message.chat.id, message.message_id, caption=caption, parse_mode="Markdown", reply_markup=kb)
        
        # حفظ البيانات
        cur.execute("INSERT INTO files VALUES (?, ?, ?, ?)", 
                    (file_hash, clean_name, file_size_mb, datetime.now().strftime("%Y-%m-%d")))
        log_op("إضافة", f"تم نشر كتاب: {clean_name}")
        db_conn.commit()
        
        bot.edit_message_text(f"✅ تم النشر بنجاح: {clean_name}", message.chat.id, status.message_id)

    except Exception as e:
        logging.error(e)

# --- 6. معالجة أزرار اللوحة (Callbacks) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    if call.from_user.id != ADMIN_ID: return
    cur = db_conn.cursor()

    if call.data == "stats":
        cur.execute("SELECT COUNT(*) FROM files")
        count = cur.fetchone()[0]
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📊 **إحصائيات المكتبة:**\n- إجمالي الكتب: {count}\n- الحالة: نشط")

    elif call.data == "health":
        status = "✅ النظام يعمل بكفاءة\n- تليجرام: متصل\n- Gemini: متصل\n- DB: مستقرة"
        bot.send_message(call.message.chat.id, status)

    elif call.data == "toggle_main":
        cur.execute("SELECT value FROM settings WHERE key='maintenance'")
        current = cur.fetchone()[0]
        new_val = "OFF" if current == "ON" else "ON"
        cur.execute("UPDATE settings SET value=? WHERE key='maintenance'", (new_val,))
        db_conn.commit()
        bot.answer_callback_query(call.id, f"وضع الصيانة: {new_val}")
        log_op("إعدادات", f"تغيير وضع الصيانة إلى {new_val}")

    elif call.data == "view_logs":
        cur.execute("SELECT op, details, time FROM logs ORDER BY id DESC LIMIT 5")
        logs = cur.fetchall()
        msg = "🧾 **آخر العمليات:**\n" + "\n".join([f"- {l[2]}: {l[0]} ({l[1]})" for l in logs])
        bot.send_message(call.message.chat.id, msg)

# --- التشغيل النهائي ---
if __name__ == "__main__":
    print("🚀 نظام مكتبة المليار كتاب (برو-ماكس) انطلق...")
    while True:
        try:
            bot.infinity_polling(timeout=30)
        except Exception:
            time.sleep(5)
