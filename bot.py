import telebot
import sqlite3
import time
import os
import threading
import random
import json
import hashlib
import logging
import io
import fitz  # PyMuPDF
import google.generativeai as genai
from telebot import apihelper

# ==========================================
# ⚙️ الإعدادات الأساسية
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "-1003254290305"
LIB_LINK = "https://t.me/Yemen_International_Library"

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TOKEN)
apihelper.SESSION_TIME_TO_LIVE = 5 * 60 # زيادة تحمل وقت الاستجابة

DB_PATH = "data/billion_lib.db"
os.makedirs("data", exist_ok=True)

# ==========================================
# 🎨 أنماط التنسيق (الجذابة)
# ==========================================
STYLES = [
    lambda n, c, d, r, w: f"📚 **{n}**\n\n🏷️ **التصنيف:** {c}\n📖 **نبذة:** {d}\n\n💡 **لماذا يستحق القراءة؟**\n{r}\n\n💎 **حكمة:** {w}",
    lambda n, c, d, r, w: f"⚡️ **{n}**\n━━━━━━━━━━━\n📂 │ {c}\n📄 │ {d}\n🎯 │ {r}\n💎 │ {w}",
    lambda n, c, d, r, w: f"┌─━━━━━━━━━─┐\n   📖 {n}\n└─━━━━━━━━━─┘\n├─❖ {c}\n├─❖ {d}\n├─❖ {r}\n└─❖ {w}"
]

# ==========================================
# 🧠 منطق الذكاء الاصطناعي (البحث والدمج السريع)
# ==========================================
def get_fast_ai_analysis(book_identifier):
    """يطلب من Gemini البحث عن الكتاب وإعطاء وصف جذاب مدمج"""
    prompt = f"""
    ابحث في معلوماتك عن كتاب بعنوان أو محتوى: '{book_identifier}'.
    أريد وصفاً جذاباً جداً للمكتبة العربية.
    أعطني النتيجة JSON فقط:
    {{
        "name": "الاسم الحقيقي الصحيح للكتاب",
        "cat": "تصنيف دقيق",
        "desc": "وصف مشوق مدمج من مراجعك",
        "reasons": "3 أسباب قوية للقراءة (نقاط)",
        "wisdom": "حكمة أو اقتباس مرتبط بالكتاب"
    }}
    """
    try:
        response = ai_model.generate_content(prompt)
        data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
        return data
    except:
        return None

def is_name_unclear(name):
    """يفحص إذا كان اسم الملف غير مفهوم (أرقام أو رموز)"""
    clean_name = name.split('.')[0]
    # إذا كان الاسم أرقام فقط أو قصير جداً
    if clean_name.isdigit() or len(clean_name) < 5:
        return True
    return False

def get_title_from_first_page(file_content):
    """يفتح أول صفحة فقط لاستخراج العنوان بسرعة"""
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        if len(doc) > 0:
            text = doc[0].get_text() # قراءة أول صفحة فقط
            doc.close()
            return text[:500] # أول 500 حرف تكفي للعنوان
    except: pass
    return ""

# ==========================================
# 🚀 محرك النشر الذكي والسريع
# ==========================================
def publisher_loop():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("SELECT hash, name, file_id FROM files WHERE status='pending' ORDER BY added_at ASC LIMIT 1")
            task = c.fetchone()
            
            if task:
                fhash, fname, fid = task
                c.execute("UPDATE files SET status='processing' WHERE hash=?", (fhash,))
                conn.commit()
                
                try:
                    file_info = bot.get_file(fid)
                    book_id_for_ai = fname.split('.')[0]
                    
                    # إذا كان الاسم غير واضح، نفتح الملف لنعرف ما بداخله
                    if is_name_unclear(fname) and file_info.file_size < 15000000:
                        downloaded = bot.download_file(file_info.file_path)
                        first_page_text = get_title_from_first_page(downloaded)
                        if first_page_text:
                            book_id_for_ai = first_page_text

                    # طلب التحليل والبحث من AI
                    ai = get_fast_ai_analysis(book_id_for_ai)
                    
                    if ai:
                        style = random.choice(STYLES)
                        caption = style(ai['name'], ai['cat'], ai['desc'], ai['reasons'], ai['wisdom'])
                        caption += f"\n\n📚 {LIB_LINK}"
                    else:
                        caption = f"📚 **{fname.split('.')[0]}**\n\n💎 {LIB_LINK}"

                    # إرسال الملف (محاولتين لضمان عدم الفشل بسبب التنسيق)
                    try:
                        bot.send_document(MAIN_CHANNEL, fid, caption=caption, parse_mode="Markdown")
                    except:
                        bot.send_document(MAIN_CHANNEL, fid, caption=caption)
                    
                    bot.send_message(ADMIN_ID, f"✅ تم النشر بنجاح: {fname}")
                    c.execute("UPDATE files SET status='published' WHERE hash=?", (fhash,))
                
                except Exception as e:
                    # في حال الفشل التام، يرسل الملف باسمه الأصلي لكي لا يتوقف
                    bot.send_document(MAIN_CHANNEL, fid, caption=f"📚 {fname}\n\n💎 {LIB_LINK}")
                    c.execute("UPDATE files SET status='failed' WHERE hash=?", (fhash,))
                
                conn.commit()
            conn.close()
        except: pass
        time.sleep(5)

# ==========================================
# 🗄️ إدارة قاعدة البيانات والاستقبال
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, 
                  status TEXT DEFAULT 'pending', added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    # تصفير أي ملفات علقت أثناء المعالجة السابقة
    c.execute("UPDATE files SET status='pending' WHERE status='processing'")
    conn.commit(); conn.close()

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    fid = message.document.file_id
    fname = message.document.file_name
    fhash = hashlib.md5(f"{fname}{fid}".encode()).hexdigest()
    
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO files (hash, name, file_id) VALUES (?,?,?)", (fhash, fname, fid))
    conn.commit(); conn.close()
    bot.reply_to(message, "⏳ تمت الإضافة للطابور.. جاري التحليل والنشر.")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=publisher_loop, daemon=True).start()
    
    # حلقة حماية من انقطاع الإنترنت
    while True:
        try:
            bot.infinity_polling(timeout=90, skip_pending_updates=True)
        except:
            time.sleep(5)
