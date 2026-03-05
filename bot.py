import telebot
import sqlite3
import time
import os
import threading
import hashlib
import json
import io
import fitz  # PyMuPDF
import google.generativeai as genai

# ==========================================
# ⚙️ الإعدادات
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "-1003254290305"
LIB_LINK = "https://t.me/Yemen_International_Library"

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TOKEN)

MAX_SIZE_MB = 20 # الحد الأقصى للتحليل بالذكاء الاصطناعي

def clean_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# ==========================================
# 🧠 محرك التحليل الأدبي
# ==========================================
def get_creative_analysis(identifier):
    prompt = f"""
    أنت خبير كتب. حلل الكتاب: '{identifier}'.
    أريد مخرجات JSON فقط، بالعربية، بأسلوب فخم:
    {{
        "real_name": "اسم الكتاب",
        "category": "التصنيف",
        "description": "نبذة مشوقة",
        "why_read": [
            {{"title": "عنوان جذاب 1", "body": "شرح مشوق 1"}},
            {{"title": "عنوان جذاب 2", "body": "شرح مشوق 2"}},
            {{"title": "عنوان جذاب 3", "body": "شرح مشوق 3"}}
        ],
        "wisdom": "اقتباس بليغ"
    }}
    """
    try:
        response = ai_model.generate_content(prompt, generation_config={"temperature": 0.8})
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(res_text)
    except: return None

def format_caption_html(ai):
    reasons_html = ""
    for r in ai['why_read']:
        reasons_html += f"• <b>{clean_html(r['title'])}</b>: {clean_html(r['body'])}\n"
    
    caption = (
        f"💎 <b>『 {clean_html(ai['real_name'])} 』</b>\n\n"
        f"📂 <b>التصنيف:</b> {clean_html(ai['category'])}\n"
        f"📖 <b>عن الكتاب:</b> {clean_html(ai['description'])}\n\n"
        f"💡 <b>لماذا يستحق القراءة؟</b>\n"
        f"{reasons_html}\n"
        f"💎 <b>حكمة:</b> <i>\"{clean_html(ai['wisdom'])}\"</i>\n\n"
        f"<u><b><a href='{LIB_LINK}'>مكتبة المليار كتاب</a></b></u>"
    )
    return caption

# ==========================================
# 🚀 محرك النشر (الذكي للأحجام الكبيرة)
# ==========================================
def publisher_loop():
    while True:
        try:
            conn = sqlite3.connect("data/billion_lib.db"); c = conn.cursor()
            c.execute("SELECT hash, name, file_id FROM files WHERE status='pending' ORDER BY added_at ASC LIMIT 1")
            task = c.fetchone()
            
            if task:
                fhash, fname, fid = task
                c.execute("UPDATE files SET status='processing' WHERE hash=?", (fhash,))
                conn.commit()
                
                try:
                    file_info = bot.get_file(fid)
                    size_mb = file_info.file_size / (1024 * 1024)
                    
                    # 🏁 الحالة 1: الكتاب كبير جداً (نشر سريع بدون تحميل)
                    if size_mb > MAX_SIZE_MB:
                        clean_name = fname.replace('_', ' ').split('.')[0]
                        fast_caption = (
                            f"📚 <b>{clean_html(clean_name)}</b>\n\n"
                            f"⚠️ <i>هذا الكتاب بحجم كبير، تم رفعه مباشرة للمكتبة.</i>\n\n"
                            f"<u><b><a href='{LIB_LINK}'>مكتبة المليار كتاب</a></b></u>"
                        )
                        bot.send_document(MAIN_CHANNEL, fid, caption=fast_caption, parse_mode="HTML")
                        bot.send_message(ADMIN_ID, f"🚀 تم نشر سريع (حجم كبير: {size_mb:.1f}MB): {fname}")
                    
                    # 🧠 الحالة 2: الكتاب حجمه مناسب للتحليل
                    else:
                        downloaded = bot.download_file(file_info.file_path)
                        identifier = fname.replace('_', ' ').split('.')[0]
                        
                        # استخراج نص إذا كان الاسم غير واضح
                        if identifier.isdigit() or len(identifier) < 8:
                            try:
                                doc = fitz.open(stream=downloaded, filetype="pdf")
                                identifier = doc[0].get_text()[:500]; doc.close()
                            except: pass
                        
                        ai_data = get_creative_analysis(identifier)
                        if ai_data:
                            final_html = format_caption_html(ai_data)
                            bot.send_document(MAIN_CHANNEL, fid, caption=final_html, parse_mode="HTML")
                        else:
                            # لو فشل الذكاء الاصطناعي نرسله بالاسم العادي
                            bot.send_document(MAIN_CHANNEL, fid, caption=f"📚 <b>{clean_html(identifier)}</b>\n\n<u><b><a href='{LIB_LINK}'>مكتبة المليار كتاب</a></b></u>", parse_mode="HTML")
                        
                        bot.send_message(ADMIN_ID, f"✅ تم التحليل والنشر: {fname}")

                    c.execute("UPDATE files SET status='published' WHERE hash=?", (fhash,))
                except Exception as e:
                    c.execute("UPDATE files SET status='failed' WHERE hash=?", (fhash,))
                
                conn.commit()
            conn.close()
        except: pass
        time.sleep(10)

# ==========================================
# 📥 البداية والاستقبال
# ==========================================
def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/billion_lib.db"); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, 
                  status TEXT DEFAULT 'pending', added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute("UPDATE files SET status='pending' WHERE status='processing'")
    conn.commit(); conn.close()

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    fhash = hashlib.md5(f"{message.document.file_name}{message.document.file_id}".encode()).hexdigest()
    conn = sqlite3.connect("data/billion_lib.db"); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO files (hash, name, file_id) VALUES (?,?,?)", 
              (fhash, message.document.file_name, message.document.file_id))
    conn.commit(); conn.close()
    bot.reply_to(message, "📥 استلمت الملف.. سأقوم بفحص الحجم والنشر فوراً!")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=publisher_loop, daemon=True).start()
    bot.infinity_polling(skip_pending_updates=True)
