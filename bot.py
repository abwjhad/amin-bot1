import telebot
import sqlite3
import requests
import time
import os
import threading
import html

# ==========================================
# ⚙️ الإعدادات (ثابتة وجاهزة)
# ==========================================
TOKEN = "6396872015:AAHQCVV0NKKAUx0jw4Un3e6YcuUGU19jd1M"
GEMINI_KEY = "AIzaSyABXhnU1tRmhuuL9FyRAtY-qGRdtQr-xiE"
ADMIN_ID = 5509592307
MAIN_CHANNEL = "@Yemen_International_Library"
LIB_LINK = "https://t.me/Yemen_International_Library"

bot = telebot.TeleBot(TOKEN)
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'billion_lib.db')

# ==========================================
# 🗄️ نظام الذاكرة المستقرة
# ==========================================
def init_db():
    conn = sqlite3.connect(db_path)
    conn.execute('''CREATE TABLE IF NOT EXISTS files 
                   (hash TEXT PRIMARY KEY, name TEXT, file_id TEXT, status TEXT)''')
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 🧠 المحرك التحليلي العميق (Gemini 1.5 Flash)
# ==========================================
def get_pro_analysis(book_name):
    """تحليل أكاديمي عميق لمنع الأوصاف المكررة"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (
        f"أنت عالم وباحث أكاديمي. حلل عنوان هذا الكتاب: '{book_name}'.\n"
        f"المطلوب منك كتابة 3 أشياء بدقة وبدون تكرار:\n"
        f"1. التصنيف: (مثلاً: فلسفة إسلامية، فيزياء الكم، رواية تاريخية، أدب رحلات).\n"
        f"2. نبذة تحليلية: اشرح 'موضوع' الكتاب وماذا يتوقع القاررئ أن يجد فيه (سطرين).\n"
        f"3. اقتباس/درة: حكمة عميقة ترتبط بموضوع الكتاب حصراً.\n\n"
        f"⚠️ تنبيه: يمنع استخدام جمل مثل 'كتاب قيم' أو 'اقرأ لترقى' أو 'منوعات'. كن محدداً وعلمياً.\n"
        f"التنسيق: التصنيف | النبذة | الاقتباس"
    )
    
    try:
        res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15).json()
        raw = res['candidates'][0]['content']['parts'][0]['text']
        parts = raw.split('|')
        return {
            "cat": html.escape(parts[0].strip()) if len(parts) > 0 else "علمي/ثقافي",
            "desc": html.escape(parts[1].strip()) if len(parts) > 1 else "دراسة تحليلية معمقة في موضوع الكتاب.",
            "wisdom": html.escape(parts[2].strip()) if len(parts) > 2 else "العلم هو القوة الحقيقية للعقل."
        }
    except:
        return {"cat": "بحث علمي", "desc": "كتاب متخصص يستعرض قضايا هامة في مجاله.", "wisdom": "البحث عن المعرفة هو أسمى الغايات."}

# ==========================================
# 📥 استقبال وجدولة (مع رد تأكيدي)
# ==========================================
@bot.message_handler(content_types=['document', 'video', 'audio'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        file_obj = message.document or message.video or message.audio
        file_name = getattr(file_obj, 'file_name', "كتاب_جديد")
        file_hash = f"{file_name}_{file_obj.file_size}"
        
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO files VALUES (?, ?, ?, ?)", (file_hash, file_name, file_obj.file_id, 'pending'))
        conn.commit()
        
        # إشعار للاستلام
        cur.execute("SELECT COUNT(*) FROM files WHERE status='pending'")
        count = cur.fetchone()[0]
        conn.close()
        
        if count % 10 == 0: # لا يزعجك مع كل ملف، بل كل 10 ملفات
            bot.send_message(ADMIN_ID, f"📥 استلمت دفعة جديدة.. إجمالي الكتب في الطابور الآن: <b>{count}</b>", parse_mode="HTML")
    except: pass

# ==========================================
# ⚙️ محرك النشر التفاعلي (إشعارات لحظية)
# ==========================================
def worker():
    publish_count = 0
    while True:
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            cur = conn.cursor()
            cur.execute("SELECT hash, name, file_id FROM files WHERE status='pending' LIMIT 1")
            task = cur.fetchone()
            
            if task:
                f_hash, f_name, f_id = task
                clean_name = f_name.replace('.pdf','').replace('.epub','').replace('_',' ').strip()
                
                # التحليل العميق
                ai = get_pro_analysis(clean_name)
                
                caption = (
                    f"📚 <b>{clean_name}</b>\n\n"
                    f"📂 <b>التصنيف:</b> {ai['cat']}\n"
                    f"📝 <b>عن الكتاب:</b> {ai['desc']}\n"
                    f"💡 <b>اقتباس:</b> <i>{ai['wisdom']}</i>\n\n"
                    f"🔖 #{ai['cat'].replace(' ','_')} #مكتبة_المليار\n"
                    f"🏛️ <a href='{LIB_LINK}'>انضم للمكتبة الرسمية</a>"
                )

                try:
                    bot.send_document(MAIN_CHANNEL, f_id, caption=caption, parse_mode="HTML")
                    cur.execute("UPDATE files SET status='published' WHERE hash=?", (f_hash,))
                    conn.commit()
                    
                    publish_count += 1
                    # 🔔 إرسال إشعار للأدمن عند كل نشر بنجاح
                    bot.send_message(ADMIN_ID, f"✅ <b>تم النشر:</b> {clean_name}\n🚀 المتبقي في الطابور: {publish_count}", parse_mode="HTML")
                    
                    time.sleep(20) # وقت آمن
                except Exception as e:
                    bot.send_message(ADMIN_ID, f"⚠️ فشل نشر '{f_name}': {str(e)}")
                    cur.execute("UPDATE files SET status='failed' WHERE hash=?", (f_hash,))
                    conn.commit()
            else:
                if publish_count > 0:
                    bot.send_message(ADMIN_ID, "🏁 <b>انتهى الطابور!</b> تم نشر جميع الكتب المجدولة.")
                    publish_count = 0
                time.sleep(15)
            conn.close()
        except:
            time.sleep(10)

# ==========================================
# 📊 لوحة التحكم المباشرة
# ==========================================
@bot.message_handler(commands=['admin', 'status'])
def report(message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect(db_path)
    p = conn.execute("SELECT COUNT(*) FROM files WHERE status='pending'").fetchone()[0]
    s = conn.execute("SELECT COUNT(*) FROM files WHERE status='published'").fetchone()[0]
    f = conn.execute("SELECT COUNT(*) FROM files WHERE status='failed'").fetchone()[0]
    conn.close()
    
    status_msg = (
        f"📊 <b>تقرير حالة النظام:</b>\n\n"
        f"⏳ في الانتظار: <code>{p}</code>\n"
        f"✅ تم بنجاح: <code>{s}</code>\n"
        f"❌ فشل النشر: <code>{f}</code>\n\n"
        f"🤖 المحرك الحالي: <b>Gemini 1.5 Flash (Academic Mode)</b>"
    )
    bot.reply_to(message, status_msg, parse_mode="HTML")

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    print("🤖 Amin-Bot Pro is Online...")
    bot.infinity_polling()
