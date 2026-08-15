from datetime import datetime, timedelta, timezone
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, jsonify, render_template_string, request
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import re

# تهيئة Firebase
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

def get_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def send_telegram_message(message, chat_id=None, reply_markup=None):
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
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
    try:
        yesterday = get_utcnow() - timedelta(days=1)
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        
        day_names_ar = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']
        day_name = day_names_ar[yesterday.weekday()]

        docs = db.collection('transactions').where(filter=firestore.FieldFilter('date', '==', yesterday_str)).stream()
        records = [doc.to_dict() for doc in docs]
        valid_records = [r for r in records if r.get('description') != 'إجازة' and float(r.get('amount', 0)) >= 0]

        if not valid_records:
            msg = f"⚠️ *تنبيه محاسبي هام!*\n\nعزيزي أبو مصعب، لاحظنا أنه لم يتم تسجيل أي حركة مالية ليوم أمس *{day_name} ({yesterday_str})*.\n\nيرجى تسجيل الحركة في أقرب وقت! 💡"
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
    <title>النظام المالي المؤسسي - أبو مصعب</title>
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
                    <h1 class="text-2xl font-black tracking-wide text-white">النظام المحاسبي الذكي - أبو مصعب</h1>
                    <p class="text-xs text-indigo-400 font-bold mt-1">V3.0 | حماية أمنية صارمة + توافق كامل مع الإصدارات الحديثة 🚀</p>
                </div>
            </div>
            <span class="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold px-4 py-2 rounded-xl flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-ping"></span> النظام يعمل بأمان تام 24/7
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
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'empty'}), 200

        chat_id = None
        if 'callback_query' in data:
            chat_id = data['callback_query']['message']['chat']['id']
        elif 'message' in data:
            chat_id = data['message']['chat']['id']

        if TELEGRAM_CHAT_ID and chat_id and str(chat_id) != str(TELEGRAM_CHAT_ID):
            return jsonify({'status': 'unauthorized'}), 403

        if 'callback_query' in data:
            cb = data['callback_query']
            message_id = cb['message']['message_id']
            data_str = cb.get('data', '')

            if data_str.startswith('reg_'):
                parts = data_str.split('_')
                tx_type = 'إيراد' if parts[1] == 'rev' else 'مصروف'
                when = parts[2]
                amount = float(parts[3])
                description = parts[4] if len(parts) > 4 else 'بدون بيان'

                target_date = get_utcnow()
                if when == 'yes':
                    target_date -= timedelta(days=1)
                date_str = target_date.strftime('%Y-%m-%d')

                db.collection('transactions').add({
                    'date': date_str,
                    'type': tx_type,
                    'amount': amount,
                    'description': description,
                    'created_at': get_utcnow()
                })

                when_name = 'اليوم' if when == 'tod' else 'أمس'
                edit_telegram_message(chat_id, message_id, f"✅ *تم الحفظ بنجاح يا أبو مصعب!*\n\n- النوع: `{tx_type}` ({when_name})\n- التاريخ: `{date_str}`\n- المبلغ: `{amount}`\n- البيان: `{description}`")
                return jsonify({'status': 'ok'})

            elif data_str.startswith('pickdate_'):
                parts = data_str.split('_', 3)
                tx_type = parts[1]
                amount = parts[2]
                description = parts[3] if len(parts) > 3 else 'بدون بيان'

                keyboard_rows = []
                day_names_ar = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']
                
                for i in range(1, 11):
                    d = get_utcnow() - timedelta(days=i)
                    d_str = d.strftime('%Y-%m-%d')
                    d_name = day_names_ar[d.weekday()]
                    keyboard_rows.append([{
                        "text": f"📅 {d_name} ({d_str})", 
                        "callback_data": f"savdate_{tx_type}_{d_str}_{amount}_{description}"
                    }])

                keyboard_rows.append([{
                    "text": "🔙 رجوع للخيار السابق", 
                    "callback_data": f"back_to_reg_{amount}_{description}"
                }])
                
                type_name = 'إيراد' if tx_type == 'rev' else 'مصروف'
                edit_telegram_message(chat_id, message_id, f"📅 *اختر اليوم المطلوب لـ {type_name} (آخر 10 أيام):*\n- المبلغ: `{amount}`\n- البيان: `{description}`", {"inline_keyboard": keyboard_rows})
                return jsonify({'status': 'ok'})

            elif data_str.startswith('savdate_'):
                parts = data_str.split('_', 4)
                tx_type = 'إيراد' if parts[1] == 'rev' else 'مصروف'
                date_str = parts[2]
                amount = float(parts[3])
                description = parts[4] if len(parts) > 4 else 'بدون بيان'

                db.collection('transactions').add({
                    'date': date_str,
                    'type': tx_type,
                    'amount': amount,
                    'description': description,
                    'created_at': get_utcnow()
                })

                edit_telegram_message(chat_id, message_id, f"✅ *تم الحفظ بنجاح بالتاريخ المختار!*\n\n- النوع: `{tx_type}`\n- التاريخ: `{date_str}`\n- المبلغ: `{amount}`\n- البيان: `{description}`")
                return jsonify({'status': 'ok'})

            elif data_str.startswith('back_to_reg_'):
                parts = data_str.split('_', 3)
                amount = parts[2]
                description = parts[3] if len(parts) > 3 else 'بدون بيان'
                
                prompt_msg = f"💰 المبلغ: `{amount}`\n📝 البيان: `{description}`\n\nاختر نوع الحركة والتاريخ للتسجيل الفوري:"
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🟢 إيراد (اليوم)", "callback_data": f"reg_rev_tod_{amount}_{description}"},
                            {"text": f"🟢 إيراد (أمس)", "callback_data": f"reg_rev_yes_{amount}_{description}"}
                        ],
                        [
                            {"text": "🔴 مصروف (اليوم)", "callback_data": f"reg_exp_tod_{amount}_{description}"},
                            {"text": "🔴 مصروف (أمس)", "callback_data": f"reg_exp_yes_{amount}_{description}"}
                        ],
                        [
                            {"text": "📅 اختيار تاريخ مخصص (إيراد)", "callback_data": f"pickdate_rev_{amount}_{description}"},
                            {"text": "📅 اختيار تاريخ مخصص (مصروف)", "callback_data": f"pickdate_exp_{amount}_{description}"}
                        ]
                    ]
                }
                edit_telegram_message(chat_id, message_id, prompt_msg, keyboard)
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_today':
                today_str = get_utcnow().strftime('%Y-%m-%d')
                docs = db.collection('transactions').where(filter=firestore.FieldFilter('date', '==', today_str)).stream()
                txs = [d.to_dict() for d in docs]
                
                msg = f"📋 *حركات اليوم ({today_str}):*\n\n"
                if not txs:
                    msg += "لا توجد حركات مسجلة ليوم اليوم حتى الآن."
                else:
                    for t in txs:
                        msg += f"• *{t.get('type')}* | المبلغ: `{t.get('amount')}` | البيان: {t.get('description', '-')}\n"
                
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔙 رجوع للقائمة الرئيسية", "callback_data": "menu_main"}],
                        [{"text": "🚪 خروج", "callback_data": "menu_exit"}]
                    ]
                }
                edit_telegram_message(chat_id, message_id, msg, keyboard)
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_missing':
                missing_days = []
                for i in range(1, 11):
                    d = get_utcnow() - timedelta(days=i)
                    d_str = d.strftime('%Y-%m-%d')
                    docs = db.collection('transactions').where(filter=firestore.FieldFilter('date', '==', d_str)).stream()
                    recs = [doc.to_dict() for doc in docs]
                    valid = [r for r in recs if r.get('description') != 'إجازة' and float(r.get('amount', 0)) >= 0]
                    if not valid:
                        missing_days.append(d_str)

                msg = "📅 *الأيام التي لم يتم تسجيل حركات لها (آخر 10 أيام):*\n\n"
                if not missing_days:
                    msg += "رائع جداً يا أبو مصعب! جميع الأيام مسجلة وليست هناك أيام ناقصة. ✅"
                else:
                    msg += "الأيام التالية خالية من الحركات:\n" + "\n".join([f"• `{day}`" for day in missing_days])

                keyboard = {
                    "inline_keyboard": [
                        [{"text": "🔙 رجوع للقائمة الرئيسية", "callback_data": "menu_main"}],
                        [{"text": "🚪 خروج", "callback_data": "menu_exit"}]
                    ]
                }
                edit_telegram_message(chat_id, message_id, msg, keyboard)
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_analytics':
                try:
                    docs = db.collection('transactions').stream()
                    all_txs = [d.to_dict() for d in docs]

                    if not all_txs:
                        msg = "📊 *التحليلات الذكية:*\n\nلا توجد بيانات كافية لإجراء التحليلات حتى الآن."
                    else:
                        day_revs = {}
                        year_revs = {}
                        day_exps = {}

                        for t in all_txs:
                            dt = t.get('date', '')
                            amt = float(t.get('amount', 0))
                            t_type = t.get('type', '')

                            if dt:
                                if t_type == 'إيراد':
                                    day_revs[dt] = day_revs.get(dt, 0.0) + amt
                                    yr = dt[:4]
                                    year_revs[yr] = year_revs.get(yr, 0.0) + amt
                                elif t_type == 'مصروف':
                                    day_exps[dt] = day_exps.get(dt, 0.0) + amt

                        max_rev_day = max(day_revs, key=day_revs.get) if day_revs else 'لا يوجد'
                        min_rev_day = min(day_revs, key=day_revs.get) if day_revs else 'لا يوجد'
                        max_year = max(year_revs, key=year_revs.get) if year_revs else 'لا يوجد'
                        min_year = min(year_revs, key=year_revs.get) if year_revs else 'لا يوجد'
                        max_exp_day = max(day_exps, key=day_exps.get) if day_exps else 'لا يوجد'

                        msg = (
                            "📊 *لوحة التحليلات والذكاء المالي:*\n\n"
                            f"📈 *أكثر يوم إيرادات (دخلاً):*\n   `{max_rev_day}` بقيمة `{day_revs.get(max_rev_day, 0):,.2f}`\n\n"
                            f"📉 *أقل يوم إيرادات (دخلاً):*\n   `{min_rev_day}` بقيمة `{day_revs.get(min_rev_day, 0):,.2f}`\n\n"
                            f"🔥 *أكثر يوم مصروفات:* \n   `{max_exp_day}` بقيمة `{day_exps.get(max_exp_day, 0):,.2f}`\n\n"
                            f"🏆 *أكثر سنة دخلاً:* سنة `{max_year}` بإجمالي `{year_revs.get(max_year, 0):,.2f}`\n\n"
                            f"📌 *أقل سنة دخلاً:* سنة `{min_year}` بإجمالي `{year_revs.get(min_year, 0):,.2f}`\n"
                        )

                    keyboard = {
                        "inline_keyboard": [
                            [{"text": "🔙 رجوع للقائمة الرئيسية", "callback_data": "menu_main"}],
                            [{"text": "🚪 خروج", "callback_data": "menu_exit"}]
                        ]
                    }
                    edit_telegram_message(chat_id, message_id, msg, keyboard)
                except Exception as e:
                    print(f"Error in analytics: {e}")
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_report':
                try:
                    docs = db.collection('transactions').stream()
                    years = set()
                    for doc in docs:
                        d = doc.to_dict()
                        if 'date' in d and len(d['date']) >= 4:
                            years.add(d['date'][:4])
                    
                    sorted_years = sorted(list(years), reverse=True)
                    if not sorted_years:
                        sorted_years = [get_utcnow().strftime('%Y')]

                    keyboard_rows = []
                    for y in sorted_years:
                        keyboard_rows.append([{"text": f"📅 سنة {y}", "callback_data": f"year_{y}"}])
                    
                    keyboard_rows.append([{"text": "🔙 رجوع", "callback_data": "menu_main"}, {"text": "🚪 خروج", "callback_data": "menu_exit"}])

                    edit_telegram_message(chat_id, message_id, "📊 *اختر السنة المالية لعرض الشهور:*", {"inline_keyboard": keyboard_rows})
                except Exception as e:
                    print(f"Error in menu_report: {e}")
                return jsonify({'status': 'ok'})

            elif data_str.startswith('year_'):
                year = data_str.split('_')[1]
                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31"
                try:
                    docs = db.collection('transactions').where(filter=firestore.FieldFilter('date', '>=', start_date)).where(filter=firestore.FieldFilter('date', '<=', end_date)).stream()
                    
                    months = set()
                    for doc in docs:
                        d = doc.to_dict()
                        if 'date' in d and len(d['date']) >= 7:
                            months.add(d['date'][5:7])

                    sorted_months = sorted(list(months), reverse=True)
                    month_names = {"01": "يناير", "02": "فبراير", "03": "مارس", "04": "أبريل", "05": "مايو", "06": "يونيو", "07": "يوليو", "08": "أغسطس", "09": "سبتمبر", "10": "أكتوبر", "11": "نوفمبر", "12": "ديسمبر"}

                    keyboard_rows = []
                    row = []
                    for m in sorted_months:
                        m_name = month_names.get(m, m)
                        row.append({"text": f"🗓️ {m_name} ({m})", "callback_data": f"month_{year}_{m}"})
                        if len(row) == 2:
                            keyboard_rows.append(row)
                            row = []
                    if row:
                        keyboard_rows.append(row)

                    keyboard_rows.append([
                        {"text": "🔙 رجوع للسنوات", "callback_data": "menu_report"},
                        {"text": "🚪 خروج", "callback_data": "menu_exit"}
                    ])

                    edit_telegram_message(chat_id, message_id, f"📅 *سنة {year}* - اختر الشهر المطلوب:", {"inline_keyboard": keyboard_rows})
                except Exception as e:
                    print(f"Error in year_ selection: {e}")
                return jsonify({'status': 'ok'})

            elif data_str.startswith('month_'):
                parts = data_str.split('_')
                year = parts[1]
                month = parts[2]
                month_names = {"01": "يناير", "02": "فبراير", "03": "مارس", "04": "أبريل", "05": "مايو", "06": "يونيو", "07": "يوليو", "08": "أغسطس", "09": "سبتمبر", "10": "أكتوبر", "11": "نوفمبر", "12": "ديسمبر"}
                m_name = month_names.get(month, month)

                prefix = f"{year}-{month}"
                start_date = f"{prefix}-01"
                end_date = f"{prefix}-31"
                
                try:
                    docs = db.collection('transactions').where(filter=firestore.FieldFilter('date', '>=', start_date)).where(filter=firestore.FieldFilter('date', '<=', end_date)).stream()
                    month_txs = []
                    rev_sum, exp_sum = 0.0, 0.0
                    for doc in docs:
                        d = doc.to_dict()
                        if 'date' in d and d['date'].startswith(prefix):
                            month_txs.append(d)
                            amt = float(d.get('amount', 0))
                            if d.get('type') == 'إيراد': rev_sum += amt
                            else: exp_sum += amt

                    month_txs.sort(key=lambda x: x['date'], reverse=True)

                    msg = f"📊 *تقرير شهر {m_name} ({year}):*\n"
                    msg += f"📈 الإيرادات: `{rev_sum:,.2f}` | 📉 المصروفات: `{exp_sum:,.2f}`\n"
                    msg += f"💰 الصافي: `{(rev_sum - exp_sum):,.2f}`\n"
                    msg += "──────────────────\n"
                    
                    if not month_txs:
                        msg += "لا توجد حركات مسجلة في هذا الشهر."
                    else:
                        for t in month_txs:
                            t_type = t.get('type')
                            type_icon = '🟢' if t_type == 'إيراد' else '🔴'
                            msg += f"{type_icon} *{t_type}* | 📅 `{t.get('date')}`\n"
                            msg += f"   💰 المبلغ: `{t.get('amount')}`\n"
                            msg += f"   📝 البيان: _{t.get('description', '-')}_\n"
                            msg += "   ▫️▫️▫️▫️▫️▫️▫️\n"

                    keyboard = {
                        "inline_keyboard": [
                            [
                                {"text": f"🔙 رجوع لسنة {year}", "callback_data": f"year_{year}"},
                                {"text": "🔙 قائمة السنوات", "callback_data": "menu_report"}
                            ],
                            [
                                {"text": "🏠 القائمة الرئيسية", "callback_data": "menu_main"},
                                {"text": "🚪 خروج", "callback_data": "menu_exit"}
                            ]
                        ]
                    }
                    edit_telegram_message(chat_id, message_id, msg, keyboard)
                except Exception as e:
                    print(f"Error in month_ report: {e}")
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_main':
                msg = "أهلاً بك يا أبو مصعب في نظامك المحاسبي الذكي 🚀\n\n• لتسجيل حركة فورية أرسل: `المبلغ البيان` (مثال: `50 غداء` أو `0 إجازة`)\n• أو اختر من القوائم أدناه:"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📋 حركات اليوم", "callback_data": "menu_today"}],
                        [{"text": "📅 الأيام الغير مسجلة", "callback_data": "menu_missing"}],
                        [{"text": "📈 التحليلات والذكاء المالي", "callback_data": "menu_analytics"}],
                        [{"text": "📊 تقرير تفصيلي", "callback_data": "menu_report"}]
                    ]
                }
                edit_telegram_message(chat_id, message_id, msg, keyboard)
                return jsonify({'status': 'ok'})

            elif data_str == 'menu_exit':
                edit_telegram_message(chat_id, message_id, "✨ تم إغلاق القائمة بنجاح يا أبو مصعب. أرسل أي نص أو `(رقم + بيان)` في أي وقت لتفعيل النظام!")
                return jsonify({'status': 'ok'})

        if 'message' in data:
            msg_obj = data['message']
            chat_id = msg_obj['chat']['id']
            text = msg_obj.get('text', '').strip()

            if text == '/start':
                msg = "أهلاً بك يا أبو مصعب في نظامك المحاسبي الذكي 🚀\n\n• لتسجيل حركة فورية اكتب مباشرة: `المبلغ البيان` (مثال: `100 مبيعات` أو `0 إجازة`)\n• أو اختر من القوائم أدناه:"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📋 حركات اليوم", "callback_data": "menu_today"}],
                        [{"text": "📅 الأيام الغير مسجلة", "callback_data": "menu_missing"}],
                        [{"text": "📈 التحليلات والذكاء المالي", "callback_data": "menu_analytics"}],
                        [{"text": "📊 تقرير تفصيلي", "callback_data": "menu_report"}]
                    ]
                }
                send_telegram_message(msg, chat_id, keyboard)
                return jsonify({'status': 'ok'})

            match = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s+(.+)$', text)
            if match:
                amount = float(match.group(1))
                description = match.group(2).strip()

                prompt_msg = f"💰 المبلغ: `{amount}`\n📝 البيان: `{description}`\n\nاختر نوع الحركة والتاريخ للتسجيل الفوري:"
                
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🟢 إيراد (اليوم)", "callback_data": f"reg_rev_tod_{amount}_{description}"},
                            {"text": f"🟢 إيراد (أمس)", "callback_data": f"reg_rev_yes_{amount}_{description}"}
                        ],
                        [
                            {"text": "🔴 مصروف (اليوم)", "callback_data": f"reg_exp_tod_{amount}_{description}"},
                            {"text": "🔴 مصروف (أمس)", "callback_data": f"reg_exp_yes_{amount}_{description}"}
                        ],
                        [
                            {"text": "📅 اختيار تاريخ مخصص (إيراد)", "callback_data": f"pickdate_rev_{amount}_{description}"},
                            {"text": "📅 اختيار تاريخ مخصص (مصروف)", "callback_data": f"pickdate_exp_{amount}_{description}"}
                        ]
                    ]
                }
                send_telegram_message(prompt_msg, chat_id, keyboard)
                return jsonify({'status': 'ok'})

            else:
                msg = f"📋 *القوائم الرئيسية للنظام المحاسبي:*\n\nاستلمت رسالتك يا أبو مصعب: _{text}_\nاختر ما تحب استعراضه:"
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📋 حركات اليوم", "callback_data": "menu_today"}],
                        [{"text": "📅 الأيام الغير مسجلة", "callback_data": "menu_missing"}],
                        [{"text": "📈 التحليلات والذكاء المالي", "callback_data": "menu_analytics"}],
                        [{"text": "📊 تقرير تفصيلي", "callback_data": "menu_report"}]
                    ]
                }
                send_telegram_message(msg, chat_id, keyboard)
                return jsonify({'status': 'ok'})

        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)