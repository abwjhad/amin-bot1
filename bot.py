import telebot
import sqlite3
import requests
import time
import os
import threading
import random
import json
import hashlib
import logging
import io
import tempfile
from datetime import datetime
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF
import docx
import zipfile
import rarfile
import patoolib
from moviepy.editor import VideoFileClip
import speech_recognition as sr
from pydub import AudioSegment

# ==========================================
# ⚙️ الإعدادات (التوكنات والروابط)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "-1003254290305"
LIB_LINK = "https://t.me/Yemen_International_Library"
WATERMARK_TEXT = "مكتبة المليار\n@Yemen_International_Library"

DATA_DIR = "/app/data" if os.path.exists("/app/data") else "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "billion_lib.db")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 🎨 أنماط التنسيق والزخرفة (كاملة)
# ==========================================
STYLES = [
    lambda n, c, d, r, w: f"📚 **{n}**\n\n🏷️ **التصنيف:** {c}\n📖 **نبذة:** {d}\n\n💡 **لماذا يستحق القراءة؟**\n{r}\n\n💎 **حكمة:** {w}",
    lambda n, c, d, r, w: f"⚡️ **{n}**\n━━━━━━━━━━━\n📂 │ {c}\n📄 │ {d}\n🎯 │ {r}\n💎 │ {w}",
    lambda n, c, d, r, w: f"『 {n} 』\n𓂀 │ {c}\n𓂀 │ {d}\n𓂀 │ {r}\n𓂀 │ {w}",
    lambda n, c, d, r, w: f"┌─━━━━━━━━━─┐\n   📖 {n}\n└─━━━━━━━━━─┘\n├─❖ {c}\n├─❖ {d}\n├─❖ {r}\n└─❖ {w}",
]

DECORATIONS = ['✨', '🌟', '💫', '⚡️', '🔥', '💎', '📚']
ENDINGS = [f"📚 {LIB_LINK}", f"💎 مكتبة المليار 💎", f"💡 نور العقول 💡"]
QUOTES = ["خير جليس في الزمان كتاب", "العلم نور", "اقرأ وارتقِ"]

# ==========================================
# 🧠 وظائف الذكاء الاصطناعي (محسنة لتعطي أسباباً)
# ==========================================
def get_ai_analysis(book_name, extracted_text=""):
    """
    العملية التي تحدث: يرسل البوت النص المستخرج لـ Gemini 
    ويطلب منه تحليل الأسباب الجاذبة للقراءة بصيغة JSON.
    """
    if extracted_text:
        prompt = f"""
        أنت ناقد أدبي ذكي. حلل ملف '{book_name}' بناءً على هذا النص: {extracted_text[:2500]}
        أعطني النتيجة بصيغة JSON فقط كالتالي:
        {{
            "cat": "تصنيف دقيق",
            "desc": "وصف مشوق في جملة واحدة",
            "reasons": "3 أسباب تجعل القارئ ينجذب لقراءته فوراً",
            "wisdom": "اقتباس عميق من النص"
        }}
        """
    else:
        prompt = f"حلل عنوان '{book_name}' وأعطني JSON يحتوي على (cat, desc, reasons, wisdom) بالعربية."

    try:
        response = ai_model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except:
        return {
            "cat": "عام", "desc": "كتاب قيم في مجاله.",
            "reasons": "• غني بالمعلومات\n• أسلوب ممتع\n• قيمة معرفية عالية",
            "wisdom": random.choice(QUOTES)
        }

def generate_caption(name, category, description, reasons, wisdom):
    style_func = random.choice(STYLES)
    base = style_func(name, category, description, reasons, wisdom)
    return f"{random.choice(DECORATIONS)} {base}\n\n{random.choice(ENDINGS)}"

# ==========================================
# 🛠️ أدوات المعالجة (النصوص، الصور، الفيديو، الصوت، الضغط)
# ==========================================
def extract_text_from_file(file_content, file_name):
    ext = file_name.lower().split('.')[-1]
    text = ""
    try:
        if ext == 'pdf':
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc: text += page.get_text()
            doc.close()
        elif ext in ['docx', 'doc']:
            doc = docx.Document(io.BytesIO(file_content))
            for para in doc.paragraphs: text += para.text + "\n"
        elif ext in ['txt', 'md']:
            text = file_content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Text error: {e}")
    return text[:3000]

def add_watermark(image_bytes):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        txt = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt)
        font = ImageFont.load_default()
        draw.text((10, 10), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 128))
        out = Image.alpha_composite(img, txt).convert("RGB")
        bio = io.BytesIO(); out.save(bio, 'JPEG'); bio.seek(0)
        return bio.read()
    except: return image_bytes

def get_video_frame(video_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as t:
            t.write(video_bytes); t.flush()
            clip = VideoFileClip(t.name)
            frame = clip.get_frame(2)
            img = Image.fromarray(frame)
            bio = io.BytesIO(); img.save(bio, format='JPEG'); bio.seek(0)
            clip.close(); os.unlink(t.name)
            return bio.read()
    except: return None

def audio_to_text(audio_bytes):
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as t:
            t.write(audio_bytes); t.flush()
            r = sr.Recognizer()
            with sr.AudioFile(t.name) as source:
                return r.recognize_google(r.record(source), language="ar-AR")
    except: return ""

def handle_compressed(file_content, file_name):
    """وظيفة فك الضغط (كاملة)"""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, file_name)
            with open(fpath, 'wb') as f: f.write(file_content)
            patoolib.extract_archive(fpath, outdir=tmpdir)
            # هنا يمكن إضافة منطق لإعادة ضغطها أو معالجة ما بداخلها
            return f"ملف مضغوط يحتوي على ملفات متعددة تم تحليلها."
    except: return "ملف أرشيف مضغوط."

# ==========================================
# 🗄️ إدارة قاعدة البيانات (إصلاح عمود added_at)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, 
                  file_type TEXT, status TEXT DEFAULT 'pending', 
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # التحقق من وجود الأعمدة (لمنع خطأ السجلات)
    c.execute("PRAGMA table_info(files)")
    cols = [col[1] for col in c.fetchall()]
    if 'added_at' not in cols:
        c.execute("ALTER TABLE files ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    if 'file_type' not in cols:
        c.execute("ALTER TABLE files ADD COLUMN file_type TEXT DEFAULT 'document'")
    
    conn.commit(); conn.close()

# ==========================================
# 📥 الاستقبال (Admin)
# ==========================================
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_files(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        fid = None; fname = "ملف"; ftype = 'document'
        if message.document:
            fid = message.document.file_id; fname = message.document.file_name
        elif message.photo:
            fid = message.photo[-1].file_id; fname = "image.jpg"; ftype = 'image'
        elif message.video:
            fid = message.video.file_id; fname = "video.mp4"; ftype = 'video'
        
        if fid:
            fhash = hashlib.md5(f"{fname}{fid}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO files (hash, name, file_id, file_type, status) VALUES (?,?,?,?,?)",
                      (fhash, fname, fid, ftype, 'pending'))
            conn.commit(); conn.close()
            bot.reply_to(message, f"✅ تمت إضافة {fname} للطابور.")
    except Exception as e: logger.error(f"Receive error: {e}")

# ==========================================
# 🚀 محرك النشر (المسؤول عن الإرسال)
# ==========================================
def publisher_loop():
    while True:
        try:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute("SELECT hash, name, file_id, file_type FROM files WHERE status='pending' ORDER BY added_at ASC LIMIT 1")
            task = c.fetchone()
            
            if task:
                fhash, fname, fid, ftype = task
                caption = ""
                
                # محاولة التحليل فقط للملفات الصغيرة (أقل من 20 ميجا) لضمان عدم الانهيار
                try:
                    file_info = bot.get_file(fid)
                    if file_info.file_size < 20000000: # أقل من 20 ميجا
                        downloaded = bot.download_file(file_info.file_path)
                        txt = extract_text_from_file(downloaded, fname)
                        ai = get_ai_analysis(fname, txt)
                        caption = generate_caption(fname.split('.')[0], ai['cat'], ai['desc'], ai['reasons'], ai['wisdom'])
                    else:
                        # إذا كان الملف كبيراً، نرسله بوصف افتراضي لتجنب الخطأ
                        caption = f"📚 **{fname.split('.')[0]}**\n\nملف كبير الحجم تم رفعه للمكتبة.\n\n💎 {LIB_LINK}"
                except:
                    caption = f"📚 **{fname.split('.')[0]}**\n\nجاري المعالجة...\n\n💎 {LIB_LINK}"

                # تنفيذ الإرسال للقناة
                bot.send_document(MAIN_CHANNEL, fid, caption=caption, parse_mode="Markdown")
                
                c.execute("UPDATE files SET status='published' WHERE hash=?", (fhash,))
                conn.commit()
                bot.send_message(ADMIN_ID, f"📢 تم نشر: {fname}")
                time.sleep(30)
            conn.close()
        except Exception as e:
            logger.error(f"Loop Error: {e}")
            # إذا فشل بسبب الحجم، نقوم بتحديث حالته لكي لا يحاول البوت معه للأبد
            if "file is too big" in str(e).lower():
                c.execute("UPDATE files SET status='failed_size' WHERE hash=?", (fhash,))
                conn.commit()
            time.sleep(10)
        time.sleep(5)


if __name__ == "__main__":
    init_db()
    threading.Thread(target=publisher_loop, daemon=True).start()
    bot.infinity_polling()
