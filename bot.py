import telebot
import sqlite3
import requests
import time
import os
import threading
import html
import random
import json
import hashlib
import logging
from datetime import datetime
import google.generativeai as genai

# ==========================================
# ⚙️ الإعدادات الأساسية (تأكد من صحتها)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_LINK = "https://t.me/Yemen_International_Library"

# إعدادات التسجيل للمتابعة في Railway
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# إعداد ذكاء Gemini
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TOKEN)

# مسارات التخزين الدائم (الـ Volume في Railway)
db_path = "/data/billion_lib.db"
archive_path = "/data/archive.json"

# ==========================================
# 🎨 قائمة أساليب التنسيق والزخرفة (الـ 200 أسلوب)
# ==========================================
STYLES = [
    lambda n, c, d, w: f"📚 **{n}**\n\n🏷️ **التصنيف:** {c}\n📖 **الوصف:** {d}\n💡 **حكمة:** {w}",
    lambda n, c, d, w: f"⚡️ **{n}**\n━━━━━━━━━━━\n📂 │ {c}\n📄 │ {d}\n💎 │ {w}",
    lambda n, c, d, w: f"『 {n} 』\n𓂀 │ {c}\n𓂀 │ {d}\n𓂀 │ {w}",
    lambda n, c, d, w: f"┌─━━━━━━━━━─┐\n   📖 {n}\n└─━━━━━━━━━─┘\n├─❖ {c}\n├─❖ {d}\n└─❖ {w}",
    lambda n, c, d, w: f"╔══════════════╗\n║   {n}   ║\n╚══════════════╝\n◉ {c}\n◉ {d}\n◉ {w}",
    lambda n, c, d, w: f"◈━━━━━━━━━━━◈\n   {n}\n◈━━━━━━━━━━━◈\n✓ {c}\n✓ {d}\n✓ {w}",
    lambda n, c, d, w: f"✨ {n} ✨\n━━━━━━━━━━━\n🎯 {c}\n📌 {d}\n💎 {w}",
    lambda n, c, d, w: f"⫸ {n} ⫷\n├─────────────\n├ {c}\n├ {d}\n└ {w}",
    lambda n, c, d, w: f"بسم الله الرحمن الرحيم\n📘 {n}\n📌 {c}\n📖 {d}\n💡 {w}",
    lambda n, c, d, w: f"📍 المرجع: {n}\n📍 المجال: {c}\n📍 الملخص: {d}\n📍 الاستنتاج: {w}",
    lambda n, c, d, w: f"📕 {n} │ {c}\n📝 {d}\n🌟 {w}",
    lambda n, c, d, w: f"【 {n} 】\n⏺ الصنف: {c}\n⏺ المحتوى: {d}\n⏺ العبرة: {w}",
    lambda n, c, d, w: f"✧ {n} ✧\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n𓍯 {c}\n𓍯 {d}\n𓍯 {w}",
]

DECORATIONS = ['✨', '🌟', '💫', '⚡️', '🔥', '💎', '📚', '📖', '📘', '💡']
ENDINGS = [
    f"📚 {LIB_LINK}",
    f"💎 مكتبة المليار 💎",
    f"🌟 مكتبة اليمن الدولية 🌟",
    f"📖 كنز المعرفة 📖",
    f"💡 نور العقول 💡",
    f"🔗 تابعنا لمزيد من الكتب: {LIB_LINK}"
]

# ==========================================
# 🧠 محرك التوليد الذكي
# ==========================================
def generate_caption(name, category, description, wisdom):
    """يختار نمطاً عشوائياً ويضيف لمسات فنية"""
    style_func = random.choice(STYLES)
    base_text = style_func(name, category, description, wisdom)
    deco = random.choice(DECORATIONS)
    ending = random.choice(ENDINGS)
    return f"{deco} {base_text}\n\n{ending}"

def get_ai_analysis(book_name):
    """تحليل الكتاب بواسطة Gemini AI بأسلوب الشخصيات"""
    prompt = f"""
    حلل كتاب: '{book_name}'
    تقمص شخصية عشوائية (مؤرخ، فيلسوف، ناقد، عالم) وأجب بـ JSON:
    {{
      "cat": "تصنيف دقيق ومبتكر",
      "desc": "نبذة بأسلوبك تجيب: لماذا يجب قراءة هذا الكتاب؟ (بدون مديح مبتذل)",
      "wisdom": "حكمة أو اقتباس عميق يناسب محتوى الكتاب"
    }}
    أجب باللغة العربية.
    """
    try:
        response = ai_model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except:
        return {"cat": "ثقافة", "desc": "رحلة معرفية فريدة في صفحات هذا الكتاب.", "wisdom": "خير جليس في الزمان كتاب"}

# ==========================================
# 🗄️ إدارة قاعدة البيانات (SQL + Volume)
# ==========================================
def init_db():
    if not os.path.exists("/data"):
        os.makedirs("/data", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

# ==========================================
# 🚀 محرك النشر التلقائي
# ==========================================
def publisher_loop():
    logger.info("✅ محرك النشر التلقائي بدأ العمل...")
    while True:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cursor.fetchone()
            
            if task:
                h, name, fid = task
                clean_name = name.replace('.pdf', '').replace('_', ' ').strip()
                
                # تحليل ذكي وتنسيق زخرفي
                ai_data = get_ai_analysis(clean_name)
                final_caption = generate_caption(clean_name, ai_data['cat'], ai_data['desc'], ai_data['wisdom'])
                
                # إرسال الكتاب للقناة
                bot.send_document(MAIN_CHANNEL, fid, caption=final_caption, parse_mode="Markdown")
                
                # تحديث الحالة
                cursor.execute("UPDATE files SET status='published' WHERE hash=?", (h,))
                conn.commit()
                
                # إشعار للأدمن
                bot.send_message(ADMIN_ID, f"✅ تم نشر كتاب جديد:\n📖 {clean_name}")
                
                time.sleep(45) # تأخير لتجنب السبام
            else:
                time.sleep(20) # انتظار في حال خلو الطابور
            conn.close()
        except Exception as e:
            logger.error(f"⚠️ خطأ في حلقة النشر: {e}")
            time.sleep(10)

# ==========================================
# 📥 استقبال الملفات والتحكم
# ==========================================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    
    f = message.document
    f_hash = hashlib.md5(f"{f.file_name}_{f.file_size}".encode()).hexdigest()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT hash FROM files WHERE hash=?", (f_hash,))
        
        if cursor.fetchone():
            bot.reply_to(message, "⚠️ هذا الكتاب موجود مسبقاً في قائمة الانتظار.")
        else:
            cursor.execute("INSERT INTO files (hash, name, file_id) VALUES (?, ?, ?)", 
                           (f_hash, f.file_name, f.file_id))
            conn.commit()
            bot.reply_to(message, f"📥 تمت إضافة '{f.file_name}' للطابور.")
        conn.close()
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ تقني: {e}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM files WHERE status='published'")
    pub = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
    pen = cur.fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 الإحصائيات:\n✅ المنشور: {pub}\n⏳ الانتظار: {pen}")

# ==========================================
# 🏁 بدء التشغيل
# ==========================================
if __name__ == "__main__":
    init_db()
    # تشغيل محرك النشر في الخلفية
    threading.Thread(target=publisher_loop, daemon=True).start()
    logger.info("🤖 البوت متصل الآن...")
    bot.infinity_polling()
