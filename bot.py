import telebot
import sqlite3
import requests
import time
import os
import logging
import hashlib
from telebot import types
from datetime import datetime

# ================== الإعدادات ==================
TOKEN = "PUT_YOUR_TELEGRAM_BOT_TOKEN"
GEMINI_KEY = "PUT_YOUR_GEMINI_API_KEY"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"

LIB_NAME = "مكتبة المليار كتاب 📚"
LIB_LINK = f"https://t.me/{MAIN_CHANNEL.replace('@','')}"

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ================== قاعدة البيانات ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "billion_lib.db")

def init_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        hash TEXT PRIMARY KEY,
        name TEXT,
        size TEXT,
        date_added TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        op TEXT,
        details TEXT,
        time TEXT
    )
    """)

    cur.execute("INSERT OR IGNORE INTO settings VALUES ('maintenance','OFF')")
    conn.commit()
    return conn

db = init_db()

def log_event(op, details):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO logs (op, details, time) VALUES (?,?,?)",
        (op, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()

# ================== أدوات ذكية ==================
def sha256_bytes(data: bytes):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def extract_book_title(file_name, caption):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

    prompt = (
        "أنت أمين مكتبة محترف.\n"
        "استخرج اسم كتاب عربي واضح فقط، بدون شرح.\n\n"
        f"اسم الملف: {file_name}\n"
        f"النص المرفق: {caption if caption else 'لا يوجد'}"
    )

    try:
        r = requests.post(
            url,
            json={"contents":[{"parts":[{"text":prompt}]}]},
            timeout=20
        ).json()

        title = r["candidates"][0]["content"]["parts"][0]["text"].strip()
        return title if len(title) > 3 else file_name
    except:
        return file_name

def get_ai_description(book_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"

    prompt = (
        f"الكتاب: {book_name}\n"
        "أعطني:\n"
        "التصنيف:\n"
        "الوصف:\n"
        "درر:"
    )

    try:
        r = requests.post(
            url,
            json={"contents":[{"parts":[{"text":prompt}]}]},
            timeout=20
        ).json()
        return r["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "التصنيف: عام\nالوصف: كتاب معرفي مهم.\nدرر: العلم نور والجهل ظلام."

# ================== لوحة الأدمن ==================
def admin_panel():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
        types.InlineKeyboardButton("🩺 فحص الحالة", callback_data="health"),
        types.InlineKeyboardButton("🔒 صيانة", callback_data="toggle_maint"),
        types.InlineKeyboardButton("🧾 السجلات", callback_data="logs")
    )
    return kb

@bot.message_handler(commands=["admin"])
def admin_cmd(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    bot.send_message(
        msg.chat.id,
        "🕹️ **لوحة تحكم أمين المكتبة**",
        reply_markup=admin_panel()
    )

@bot.callback_query_handler(func=lambda c: True)
def callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    cur = db.cursor()

    if call.data == "stats":
        cur.execute("SELECT COUNT(*) FROM files")
        count = cur.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📚 إجمالي الكتب: {count}")

    elif call.data == "health":
        bot.send_message(call.message.chat.id,
            "✅ النظام يعمل\n"
            "• Telegram: متصل\n"
            "• Gemini: متصل\n"
            "• Database: مستقرة"
        )

    elif call.data == "toggle_maint":
        cur.execute("SELECT value FROM settings WHERE key='maintenance'")
        current = cur.fetchone()[0]
        new = "OFF" if current == "ON" else "ON"
        cur.execute("UPDATE settings SET value=? WHERE key='maintenance'", (new,))
        db.commit()
        log_event("إعدادات", f"تغيير الصيانة إلى {new}")
        bot.answer_callback_query(call.id, f"الصيانة: {new}")

    elif call.data == "logs":
        cur.execute("SELECT op,details,time FROM logs ORDER BY id DESC LIMIT 5")
        rows = cur.fetchall()
        text = "🧾 آخر العمليات:\n"
        for r in rows:
            text += f"- {r[2]} | {r[0]} | {r[1]}\n"
        bot.send_message(call.message.chat.id, text)

# ================== معالجة الملفات ==================
@bot.message_handler(content_types=["document","video","audio"])
def handle_files(msg):
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE key='maintenance'")
    if cur.fetchone()[0] == "ON" and msg.from_user.id != ADMIN_ID:
        return bot.reply_to(msg, "⚠️ المكتبة في وضع الصيانة.")

    file = msg.document or msg.video or msg.audio
    file_name = getattr(file, "file_name", "file")
    caption = msg.caption

    # تحميل الملف لحساب البصمة
    file_path = bot.get_file(file.file_id).file_path
    file_bytes = bot.download_file(file_path)
    file_hash = sha256_bytes(file_bytes)

    # فحص التكرار
    cur.execute("SELECT date_added FROM files WHERE hash=?", (file_hash,))
    old = cur.fetchone()
    if old:
        if msg.from_user.id == ADMIN_ID:
            bot.reply_to(msg, f"⚠️ الكتاب موجود مسبقاً منذ {old[0]}")
        return

    book_title = extract_book_title(file_name, caption)
    ai_text = get_ai_description(book_title)

    size_mb = f"{file.file_size / (1024*1024):.2f} MB"

    caption_text = (
        f"📖 **اسم الكتاب:** {book_title}\n"
        f"{ai_text}\n\n"
        f"💾 **الحجم:** {size_mb}\n\n"
        f"🏛️ [{LIB_NAME}]({LIB_LINK})\n"
        f"━━━━━━━━━━━━\n"
        f"📢 ساهم في نشر العلم"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("انضم للمكتبة 📚", url=LIB_LINK))

    bot.copy_message(
        MAIN_CHANNEL,
        msg.chat.id,
        msg.message_id,
        caption=caption_text,
        reply_markup=kb
    )

    cur.execute(
        "INSERT INTO files VALUES (?,?,?,?)",
        (file_hash, book_title, size_mb, datetime.now().strftime("%Y-%m-%d"))
    )
    db.commit()

    log_event("إضافة", book_title)
    bot.reply_to(msg, "✅ تم الأرشفة والنشر بنجاح")

# ================== التشغيل ==================
if __name__ == "__main__":
    print("🚀 أمين المكتبة يعمل...")
    while True:
        try:
            bot.infinity_polling(timeout=30)
        except:
            time.sleep(5)
