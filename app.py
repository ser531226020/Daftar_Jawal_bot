from datetime import datetime, timedelta
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, render_template_string, request
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import re

if 'FIREBASE_CONFIG_JSON' in os.environ:
    try:
        raw_config = os.environ['FIREBASE_CONFIG_JSON'].strip()
        if raw_config.startswith("'") and raw_config.endswith("'"):
            raw_config = raw_config[1:-1]
        elif raw_config.startswith('"') and raw_config.endswith('"'):
            raw_config = raw_config[1:-1]
            
        firebase_config = json.loads(raw_config)
        cred = credentials.Certificate(firebase_config)
    except Exception as e:
        raise ValueError(f"فشل قراءة متغير البيئة FIREBASE_CONFIG_JSON كـ JSON صحيح: {e}")
elif os.path.exists("serviceAccountKey.json"):
    cred = credentials.Certificate("serviceAccountKey.json")
else:
    raise FileNotFoundError("تنبيه هام: لم يتم العثور على ملف serviceAccountKey.json محلياً ولا متغير البيئة!")

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred, {"projectId": "turki-2030"})

db = firestore.client()
app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

def send_telegram_message(message, chat_id=None, reply_markup=None):
    """إرسال رسالة أو لوحة مفاتيح تفاعلية عبر بوت تيليجرام"""
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        print("تنبيه: توكن تيليجرام أو معرف الشات غير متوفر لإرسال الرسالة.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في إرسال رسالة تيليجرام: {e}")
        return False

def edit_telegram_message(chat_id, message_id, text, reply_markup=None):
    """تعديل رسالة موجودة في تيليجرام للتنقل السلس والسريع"""
    if not TELEGRAM_BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"خطأ في تعديل رسالة تيليجرام: {e}")
        return False

def daily_check_yesterday_transaction():
    """فحص ما إذا تم تسجيل حركة لليوم السابق، وإن لم يوجد يرسل تنبيه تيليجرام"""
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        # ترتيب الأسبوع الحقيقي في بايثون: weekday(): 0=الإثنين ... 6=الأحد
        # لتحقيق توافق تام مع التقويم العربي:
        day_names_ar = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
        day_name = day_names_ar[yesterday.weekday()]

        docs = db.collection('transactions').where('date', '==', yesterday_str).stream()
        records = [doc.to_dict() for doc in docs]
        valid_records = [r for r in records if r.get('description') != 'إجازة' and float(r.get('amount', 0)) >= 0]

        if not valid_records:
            msg = f"⚠️ *تنبيه محاسبي هام!*\n\nعزيزي تركي، لاحظنا أنه لم يتم تسجيل أي حركة مالية ليوم أمس *{day_name} ({yesterday_str})*.\n\nيرجى تسجيل الحركة أو مراجعة النظام في أقرب وقت! 💡"
            send_telegram_message(msg)
    except Exception as e:
        print(f"خطأ في الفحص اليومي: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(func=daily_check_yesterday_transaction, trigger="cron", hour=0, minute=10)
scheduler.start()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>النظام المالي المؤسسي - مع إدارة تيليجرام الذكية</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;900&display=swap" rel="stylesheet">
    <style> body { font-family: 'Cairo', sans-serif; } </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-8 px-4">
    <div class="max-w-7xl mx-auto space-y-6">
        <div class="bg-slate-900/90 backdrop-blur-xl shadow-2xl rounded-3xl p-6 border border-slate-800 flex flex-wrap justify-between items-center gap-4">
            <div class="flex items-center space-x-4 space-x-reverse">
                <div class="w-14 h-14 bg-gradient-to-tr from-indigo-600 to-violet-600 rounded-2xl flex items-center justify-center shadow-xl shadow-indigo-600/30 text-3xl font-black text-white">ط</div>
                <div>
                    <h1 class="text-2xl font-black tracking-wide text-white">النظام المحاسبي الذكي بوتي</h1>
                    <p class="text-xs text-indigo-400 font-bold mt-1">V2.8 | مطابقة التقويم الحقيقي وأسماء الأيام بدقة</p>
                </div>
            </div>
            <span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span> التقويم الحقيقي مفعل 🚀
            </span>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """المعالج الذكي السريع لرسائل وأزرار تيليجرام"""
    try:
        data = request.json
        print("Telegram incoming data:", json.dumps(data, ensure_ascii=False))

        if 'callback_query' in data:
            cb = data['callback_query']
            chat_id = cb['message']['chat']['id']
            message_id = cb['message']['message_id']
            data_str = cb.get('data', '')

            # تسجيل الحركة المباشرة (اليوم أو أمس)
            if data_str.startswith('reg_'):
                parts = data_str.split('_')
                tx_type = 'إيراد' if parts[1] == 'rev' else 'مصروف'
                when = parts[2]
                amount = float(parts[3])
                description = parts[4] if len(parts) > 4 else 'بدون بيان'

                target_date = datetime.utcnow()
                if when == 'yes':
                    target_date -= timedelta(days=1)
                date_str = target_date.strftime('%Y-%m-%d')

                db.collection('transactions').add({
                    'date': date_str,
                    'type': tx_type,
                    'amount': amount,
                    'description': description,
                    'created_at': datetime.utcnow()
                })

                when_name = 'اليوم' if when == 'tod' else 'أمس'
                edit_telegram_message(chat_id, message_id, f"✅ *تم الحفظ بنجاح!*\n\n- النوع: `{tx_type}` ({when_name})\n- التاريخ: `{date_str}`\n- المبلغ: `{amount}`\n- البيان: `{description}`")
                return jsonify({'status': 'ok'})

            # فتح قائمة اختيار تاريخ مخصص للحركة (أزرار الأيام السابقة بال