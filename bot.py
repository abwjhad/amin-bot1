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
# ⚙️ الإعدادات (تم دمج التوكنات الخاصة بك)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_LINK = "https://t.me/Yemen_International_Library"
WATERMARK_TEXT = "مكتبة المليار\n@Yemen_International_Library"

# إعداد المسارات (متوافق مع Railway Volume)
# نستخدم /data إذا كان موجوداً (للإنتاج)، وإلا نستخدم مجلد محلي
if os.path.exists("/data"):
    DATA_DIR = "/data"
else:
    DATA_DIR = "data"
    os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "billion_lib.db")

# إعداد السجلات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# إعداد الذكاء الاصطناعي
genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 🎨 أنماط التنسيق والزخرفة (مختارات مميزة)
# ==========================================
STYLES = [
    lambda n, c, d, w: f"📚 **{n}**\n\n🏷️ **التصنيف:** {c}\n📖 **الوصف:** {d}\n💡 **حكمة:** {w}",
    lambda n, c, d, w: f"⚡️ **{n}**\n━━━━━━━━━━━\n📂 │ {c}\n📄 │ {d}\n💎 │ {w}",
    lambda n, c, d, w: f"『 {n} 』\n𓂀 │ {c}\n𓂀 │ {d}\n𓂀 │ {w}",
    lambda n, c, d, w: f"┌─━━━━━━━━━─┐\n   📖 {n}\n└─━━━━━━━━━─┘\n├─❖ {c}\n├─❖ {d}\n└─❖ {w}",
    lambda n, c, d, w: f"✨ {n} ✨\n━━━━━━━━━━━\n🎯 {c}\n📌 {d}\n💎 {w}",
    lambda n, c, d, w: f"📍 المرجع: {n}\n📍 المجال: {c}\n📍 الملخص: {d}\n📍 الاستنتاج: {w}",
    lambda n, c, d, w: f"【 {n} 】\n⏺ الصنف: {c}\n⏺ المحتوى: {d}\n⏺ العبرة: {w}",
    lambda n, c, d, w: f"✧ {n} ✧\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n𓍯 {c}\n𓍯 {d}\n𓍯 {w}",
    lambda n, c, d, w: f"┌─────────────────┐\n│   {n}   │\n├─────────────────┤\n│ 🏷️ {c} │\n│ 📝 {d} │\n│ 💎 {w} │\n└─────────────────┘",
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
QUOTES = ["خير جليس في الزمان كتاب", "العلم نور", "اطلب العلم من المهد إلى اللحد", "اقرأ وارتقِ"]

# ==========================================
# 🧠 وظائف الذكاء الاصطناعي والتحليل
# ==========================================
def get_ai_analysis(book_name, extracted_text=""):
    """تحليل المحتوى باستخدام Gemini"""
    if extracted_text:
        prompt = f"""
        الكتاب/الملف: '{book_name}'
        مقتطف من المحتوى: {extracted_text[:2000]}
        
        بناءً على الاسم والمحتوى، استخرج بصيغة JSON فقط:
        {{
            "cat": "تصنيف دقيق (سياسي، علمي، ديني...)",
            "desc": "وصف جذاب ومختصر للمحتوى (جملتين)",
            "wisdom": "حكمة عميقة تناسب الموضوع"
        }}
        """
    else:
        prompt = f"حلل عنوان الكتاب '{book_name}' وأعطني JSON: {{'cat': '..', 'desc': '..', 'wisdom': '..'}} بالعربية."

    try:
        response = ai_model.generate_content(prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except:
        return {
            "cat": "عام",
            "desc": f"محتوى مميز بعنوان {book_name} يستحق الاطلاع.",
            "wisdom": random.choice(QUOTES)
        }

def generate_caption(name, category, description, wisdom):
    """توليد وصف مزخرف"""
    style_func = random.choice(STYLES)
    base = style_func(name, category, description, wisdom)
    deco = random.choice(DECORATIONS)
    end = random.choice(ENDINGS)
    return f"{deco} {base}\n\n{end}"

# ==========================================
# 🛠️ أدوات المعالجة (نص، صور، فيديو، صوت)
# ==========================================
def extract_text_from_file(file_content, file_name):
    """استخراج النصوص من ملفات مختلفة"""
    ext = file_name.lower().split('.')[-1]
    text = ""
    try:
        if ext == 'pdf':
            doc = fitz.open(stream=file_content, filetype="pdf")
            for page in doc:
                text += page.get_text()
                if len(text) > 2000: break
        elif ext in ['docx', 'doc']:
            doc = docx.Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif ext in ['txt', 'md']:
            text = file_content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Text extraction error: {e}")
    return text[:3000]

def add_watermark(image_bytes):
    """إضافة علامة مائية للصورة"""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        txt = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(txt)
        
        # محاولة تحميل خط، أو استخدام الافتراضي
        try:
            font = ImageFont.truetype("arial.ttf", int(img.width / 20))
        except:
            font = ImageFont.load_default()

        # رسم النص في المنتصف السفلي
        bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = (img.width - w) / 2, img.height - h - 20
        
        # خلفية شبه شفافة للنص
        draw.rectangle([x-10, y-10, x+w+10, y+h+10], fill=(0, 0, 0, 100))
        draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, 200))
        
        out = Image.alpha_composite(img, txt).convert("RGB")
        bio = io.BytesIO()
        out.save(bio, 'JPEG', quality=90)
        bio.seek(0)
        return bio.read()
    except Exception as e:
        logger.error(f"Watermark error: {e}")
        return image_bytes

def get_video_frame(video_bytes):
    """استخراج لقطة من الفيديو لوضع العلامة المائية عليها"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as t:
            t.write(video_bytes)
            t.flush()
            clip = VideoFileClip(t.name)
            frame = clip.get_frame(2) # ثانية رقم 2
            img = Image.fromarray(frame)
            bio = io.BytesIO()
            img.save(bio, format='JPEG')
            bio.seek(0)
            clip.close()
            os.unlink(t.name)
            return bio.read()
    except:
        return None

def audio_to_text(audio_bytes):
    """تحويل الصوت إلى نص (لأغراض التحليل)"""
    try:
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as t:
            t.write(audio_bytes)
            t.flush()
            r = sr.Recognizer()
            with sr.AudioFile(t.name) as source:
                audio = r.record(source)
                return r.recognize_google(audio, language="ar-AR")
    except:
        return ""

# ==========================================
# 🗄️ إدارة قاعدة البيانات (SQL)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # إنشاء الجدول مع دعم التحديثات القديمة
    c.execute('''CREATE TABLE IF NOT EXISTS files 
                 (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, 
                  file_type TEXT, status TEXT DEFAULT 'pending', 
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # التحقق من وجود الأعمدة الجديدة (في حال كان هناك قاعدة بيانات قديمة)
    try:
        c.execute("SELECT file_type FROM files LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE files ADD COLUMN file_type TEXT DEFAULT 'document'")
        c.execute("ALTER TABLE files ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        logger.info("🛠️ تم تحديث قاعدة البيانات وإضافة الأعمدة الجديدة.")
        
    conn.commit()
    conn.close()
    logger.info(f"✅ قاعدة البيانات جاهزة في: {DB_PATH}")

# ==========================================
# 📥 استقبال الملفات (Admin Only)
# ==========================================
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def handle_files(message):
    if message.from_user.id != ADMIN_ID: return

    try:
        # تحديد نوع الملف
        ftype = 'document'
        fname = "ملف"
        fid = None
        
        if message.document:
            fid = message.document.file_id
            fname = message.document.file_name
        elif message.photo:
            fid = message.photo[-1].file_id
            fname = f"IMG_{datetime.now().strftime('%Y%m%d')}.jpg"
            ftype = 'image'
        elif message.video:
            fid = message.video.file_id
            fname = message.video.file_name or "video.mp4"
            ftype = 'video'
        elif message.audio:
            fid = message.audio.file_id
            fname = message.audio.file_name or "audio.mp3"
            ftype = 'audio'

        if not fid: return

        # منع التكرار
        fhash = hashlib.md5(f"{fname}{fid}".encode()).hexdigest()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT hash FROM files WHERE hash=?", (fhash,))
        
        if c.fetchone():
            bot.reply_to(message, "⚠️ هذا الملف موجود بالفعل في الطابور.")
        else:
            c.execute("INSERT INTO files (hash, name, file_id, file_type, status) VALUES (?,?,?,?,?)",
                      (fhash, fname, fid, ftype, 'pending'))
            conn.commit()
            bot.reply_to(message, f"✅ تمت إضافة **{fname}** ({ftype}) للطابور.")
        conn.close()
        
    except Exception as e:
        logger.error(f"Error receiving file: {e}")
        bot.reply_to(message, "❌ حدث خطأ أثناء الحفظ.")

# ==========================================
# 🚀 محرك النشر التلقائي
# ==========================================
def publisher_loop():
    logger.info("🚀 بدء محرك النشر...")
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # جلب أقدم ملف "pending"
            c.execute("SELECT hash, name, file_id, file_type FROM files WHERE status='pending' ORDER BY added_at ASC LIMIT 1")
            task = c.fetchone()
            
            if task:
                fhash, fname, fid, ftype = task
                logger.info(f"📤 جاري معالجة: {fname}")
                
                # تحميل الملف
                file_info = bot.get_file(fid)
                downloaded = bot.download_file(file_info.file_path)
                
                # 1. معالجة المحتوى (استخراج نص / علامة مائية)
                extracted_text = ""
                final_media = downloaded
                
                if ftype == 'document':
                    extracted_text = extract_text_from_file(downloaded, fname)
                elif ftype == 'image':
                    final_media = add_watermark(downloaded)
                elif ftype == 'video':
                    frame = get_video_frame(downloaded)
                    if frame: final_media = add_watermark(frame) # نستخدم الإطار للصورة المصغرة أو نرسل الفيديو كما هو
                elif ftype == 'audio':
                    extracted_text = audio_to_text(downloaded)

                # 2. تحليل AI
                clean_name = fname.replace('.pdf', '').replace('.docx', '').replace('_', ' ')
                ai_data = get_ai_analysis(clean_name, extracted_text)
                
                # 3. صياغة المنشور
                caption = generate_caption(clean_name, ai_data['cat'], ai_data['desc'], ai_data['wisdom'])
                
                # 4. الإرسال للقناة
                try:
                    if ftype == 'image':
                        bot.send_photo(MAIN_CHANNEL, final_media, caption=caption, parse_mode="Markdown")
                    elif ftype == 'video':
                        bot.send_video(MAIN_CHANNEL, fid, caption=caption, parse_mode="Markdown")
                    elif ftype == 'audio':
                        bot.send_audio(MAIN_CHANNEL, fid, caption=caption, parse_mode="Markdown")
                    else:
                        bot.send_document(MAIN_CHANNEL, fid, caption=caption, parse_mode="Markdown")
                    
                    # تحديث الحالة
                    c.execute("UPDATE files SET status='published' WHERE hash=?", (fhash,))
                    conn.commit()
                    bot.send_message(ADMIN_ID, f"📢 تم نشر: {fname}")
                    time.sleep(40) # انتظار بين المنشورات
                    
                except Exception as send_err:
                    logger.error(f"Failed to send {fname}: {send_err}")
                    c.execute("UPDATE files SET status='failed' WHERE hash=?", (fhash,))
                    conn.commit()
            
            else:
                time.sleep(20) # الانتظار عند خلو الطابور
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Publisher Loop Error: {e}")
            time.sleep(10)

# ==========================================
# 🕹️ أوامر التحكم
# ==========================================
@bot.message_handler(commands=['stats'])
def stats(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM files GROUP BY status")
    data = dict(c.fetchall())
    conn.close()
    text = f"📊 **الإحصائيات:**\n✅ منشور: {data.get('published', 0)}\n⏳ انتظار: {data.get('pending', 0)}\n❌ فشل: {data.get('failed', 0)}"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['clear'])
def clear_failed(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM files WHERE status='failed'")
    conn.commit()
    conn.close()
    bot.reply_to(message, "🗑️ تم مسح الملفات الفاشلة.")

# ==========================================
# 🏁 التشغيل
# ==========================================
if __name__ == "__main__":
    init_db()
    # تشغيل عملية النشر في الخلفية
    t = threading.Thread(target=publisher_loop, daemon=True)
    t.start()
    
    logger.info("🤖 البوت يعمل الآن ويستقبل الملفات...")
    bot.infinity_polling()
