import telebot
import sqlite3
import requests
import time
import os
import logging
from telebot import types
from datetime import datetime

# ================== الإعدادات ==================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
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
    # تعديل جدول الملفات ليعتمد على البصمة الوهمية (اسم + حجم)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        file_id TEXT PRIMARY KEY,
        name TEXT,
        size TEXT,
        date_added TEXT
    )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("INSERT OR IGNORE INTO settings VALUES ('maintenance','OFF')")
    conn.commit()
    return conn

db = init_db()

# ================== أدوات ذكية (بدون تحميل الملف) ==================

def get_ai_details(book_title):
    """جلب التصنيف والوصف والدرر من Gemini"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_KEY}"
    prompt = (
        f"أنت أمين مكتبة خبير. الكتاب هو: '{book_title}'.\n"
        "أعطني الرد بالتنسيق التالي فقط:\n"
        "🏷️ **التصنيف:** [نوع الكتاب]\n"
        "📝 **الوصف:** [وصف بليغ سطرين]\n"
        "💎 **درر:** [مقولة عالمية أو يمنية مسجوعة عن العلم]"
    )
    try:
        r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=15).json()
        return r["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return "🏷️ **التصنيف:** عام\n📝 **الوصف:** كتاب قيم ومفيد.\n💎 **درر:** العلم يرفع بيوتاً لا عماد لها."

# ================== معالجة الملفات (نظام البصمة السريع) ==================

@bot.message_handler(content_types=["document", "video", "audio"])
def handle_files(msg):
    cur = db.cursor()
    cur.execute("SELECT value FROM settings WHERE key='maintenance'")
    if cur.fetchone()[0] == "ON" and msg.from_user.id != ADMIN_ID:
        return bot.reply_to(msg, "⚠️ المكتبة في وضع الصيانة حالياً.")

    file = msg.document or msg.video or msg.audio
    file_name = getattr(file, "file_name", "بدون اسم")
    
    # تنظيف الاسم من الامتدادات
    clean_name = file_name.replace(".pdf","").replace(".epub","").replace(".mp4","").replace("_"," ").strip()
    size_mb = f"{file.file_size / (1024*1024):.2f} MB"

    # [💡 التعديل الجوهري] منع التكرار باستخدام (اسم الكتاب + حجمه)
    # هذا يمنع التكرار دون الحاجة لتحميل الملف
    file_signature = f"{clean_name}_{file.file_size}"

    cur.execute("SELECT date_added FROM files WHERE file_id=?", (file_signature,))
    exists = cur.fetchone()

    if exists:
        if msg.from_user.id == ADMIN_ID:
            bot.reply_to(msg, f"⚠️ هذا الكتاب موجود مسبقاً في القناة منذ {exists[0]}")
        return

    # جلب البيانات من الذكاء الاصطناعي بناءً على الاسم فقط
    status_msg = bot.reply_to(msg, "⏳ جاري استخراج الدرر والأرشفة...")
    ai_content = get_ai_details(clean_name)

    # تنسيق المنشور
    caption_text = (
        f"📖 **اسم الكتاب:** {clean_name}\n"
        f"{ai_content}\n\n"
        f"💾 **حجم الملف:** {size_mb}\n\n"
        f"🏛️ **[{LIB_NAME}]({LIB_LINK})**\n"
        f"━━━━━━━━━━━━\n"
        f"📢 ساهم في نشر العلم والمعرفة"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("انضم للمكتبة 📚", url=LIB_LINK))

    try:
        # النشر في القناة
        bot.copy_message(
            MAIN_CHANNEL,
            msg.chat.id,
            msg.message_id,
            caption=caption_text,
            reply_markup=kb,
            parse_mode="Markdown"
        )

        # حفظ في قاعدة البيانات
        cur.execute("INSERT INTO files VALUES (?,?,?,?)", 
                    (file_signature, clean_name, size_mb, datetime.now().strftime("%Y-%m-%d")))
        db.commit()
        
        bot.edit_message_text("✅ تم الأرشفة والنشر بنجاح!", msg.chat.id, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ خطأ في النشر: {e}", msg.chat.id, status_msg.message_id)

# ================== لوحة التحكم (Admin) ==================
@bot.message_handler(commands=["admin"])
def admin_cmd(msg):
    if msg.from_user.id != ADMIN_ID: return
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
        types.InlineKeyboardButton("🔒 وضع الصيانة", callback_data="toggle_maint")
    )
    bot.send_message(msg.chat.id, "🕹️ لوحة تحكم المكتبة:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: True)
def admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    cur = db.cursor()
    if call.data == "stats":
        cur.execute("SELECT COUNT(*) FROM files")
        count = cur.fetchone()[0]
        bot.send_message(call.message.chat.id, f"📚 إجمالي الكتب المؤرشفة: {count}")
    elif call.data == "toggle_maint":
        cur.execute("SELECT value FROM settings WHERE key='maintenance'")
        new = "OFF" if cur.fetchone()[0] == "ON" else "ON"
        cur.execute("UPDATE settings SET value=?", (new,))
        db.commit()
        bot.answer_callback_query(call.id, f"وضع الصيانة الآن: {new}")

if __name__ == "__main__":
    print("🚀 البوت يعمل الآن بنظام البصمة السريعة...")
    bot.infinity_polling()
