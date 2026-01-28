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
# ⚙️ الإعدادات الأساسية
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_LINK = "https://t.me/Yemen_International_Library"

# إعدادات التسجيل (Logging) للمتابعة في Railway
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# إعداد جمناي
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TOKEN)

# --- مسارات الـ Volume (تعديل هام للاستمرارية) ---
db_path = "/data/billion_lib.db"
archive_path = "/data/archive.json"

# ==========================================
# 🎭 نظام الأساليب الذكي (نموذج من الـ 50 أسلوباً)
# ==========================================
PROMPT_STYLES = [
    {"id": 1, "name": "عالم أنثروبولوجيا", "template": "حلل كتاب '{book}' كظاهرة مجتمعية. ما الذي يكشفه عن الثقافة؟"},
    {"id": 2, "name": "مخترع عبقري", "template": "كيف نحول أفكار '{book}' لاختراعات عملية؟"},
    {"id": 3, "name": "رحالة مستكشف", "template": "وصف رحلتك الاستكشافية عبر كتاب '{book}' والكنوز التي وجدتها."},
    {"id": 4, "name": "طبيب نفسي", "template": "شخص الفائدة النفسية لكتاب '{book}' وكيف يداوي العقل؟"},
    {"id": 5, "name": "مهندس معماري", "template": "صمم البناء الفكري لكتاب '{book}' والأسس التي يرتكز عليها."},
    # ... يمكن إضافة بقية الـ 50 أسلوباً هنا بنفس النمط
]

# ==========================================
# 📁 نظام الأرشيف وإدارة البيانات
# ==========================================
class PersistentArchive:
    def __init__(self):
        if not os.path.exists("/data"):
            os.makedirs("/data", exist_ok=True)
        self.load()

    def load(self):
        try:
            if os.path.exists(archive_path):
                with open(archive_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            else:
                self.data = {"books": [], "published_count": 0}
        except:
            self.data = {"books": [], "published_count": 0}

    def save(self):
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

archive = PersistentArchive()

# ==========================================
# 🧠 محرك الذكاء الاصطناعي (الأسلوب المطور)
# ==========================================
def get_smart_analysis(book_name):
    style = random.choice(PROMPT_STYLES)
    prompt = f"""
    أنت تتحدث بأسلوب: {style['name']}
    حلل كتاب: '{book_name}'
    المطلوب رد JSON حصراً بالصيغة التالية:
    {{
      "cat": "تصنيف دقيق ومبتكر",
      "desc": "نبذة تجيب: لماذا يحتاج القارئ هذا الكتاب؟ وما التغيير الذي سيحدث له؟ (بدون عبارات مكررة)",
      "wisdom": "درة أو حكمة فريدة تناسب الكتاب"
    }}
    """
    try:
        response = ai_model.generate_content(prompt)
        # تنظيف النص لضمان أنه JSON صالح
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text), style['name']
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return {
            "cat": "ثقافة ومعرفة",
            "desc": "كتاب يفتح آفاقاً جديدة في رحلتك المعرفية ويضيف لعمقك الفكري.",
            "wisdom": "خير جليس في الزمان كتاب"
        }, "أسلوب عام"

# ==========================================
# 🛠️ تهيئة قاعدة البيانات ووظائف البوت
# ==========================================
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT)''')
    conn.commit()
    conn.close()

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    
    f = message.document
    f_hash = hashlib.md5(f"{f.file_name}_{f.file_size}".encode()).hexdigest()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT hash FROM files WHERE hash=?", (f_hash,))
    
    if cursor.fetchone():
        bot.reply_to(message, "⚠️ هذا الكتاب موجود مسبقاً.")
    else:
        cursor.execute("INSERT INTO files VALUES (?, ?, ?, ?)", (f_hash, f.file_name, f.file_id, 'pending'))
        conn.commit()
        bot.reply_to(message, f"✅ تمت الجدولة: {f.file_name}")
        archive.data["books"].append({"name": f.file_name, "hash": f_hash})
        archive.save()
    conn.close()

# ==========================================
# 🚀 محرك النشر التلقائي
# ==========================================
def publisher_loop():
    while True:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cursor.fetchone()
            
            if task:
                h, name, fid = task
                clean_name = name.replace('.pdf', '').replace('_', ' ')
                
                ai_data, style_name = get_smart_analysis(clean_name)
                
                caption = f"""
📚 <b>{clean_name}</b>

📂 <b>التصنيف:</b> {ai_data.get('cat', 'معرفة')}

📖 <b>لماذا تقرأ هذا الكتاب؟</b>
{ai_data.get('desc', '')}

💎 <b>درر:</b> <i>{ai_data.get('wisdom', '')}</i>

🎭 <b>الأسلوب:</b> {style_name}
🏛️ <a href='{LIB_LINK}'>مكتبة المليار كتاب</a>
                """
                
                bot.send_document(MAIN_CHANNEL, fid, caption=caption, parse_mode="HTML")
                
                cursor.execute("UPDATE files SET status='published' WHERE hash=?", (h,))
                conn.commit()
                archive.data["published_count"] += 1
                archive.save()
                
                bot.send_message(ADMIN_ID, f"✅ تم نشر: {clean_name}\n🎭 الأسلوب: {style_name}")
                time.sleep(30) # فاصل زمني بين المنشورات
            else:
                time.sleep(10)
            conn.close()
        except Exception as e:
            logger.error(f"Publisher Loop Error: {e}")
            time.sleep(10)

# ==========================================
# 📊 أوامر التحكم
# ==========================================
@bot.message_handler(commands=['stats'])
def send_stats(message):
    if message.from_user.id != ADMIN_ID: return
    total = archive.data["published_count"]
    bot.reply_to(message, f"📊 إحصائيات الأرشيف الدائم:\n✅ الكتب المنشورة: {total}")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=publisher_loop, daemon=True).start()
    logger.info("🤖 البوت يعمل الآن بالنظام المطور...")
    bot.infinity_polling()
