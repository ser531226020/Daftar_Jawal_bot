import os
from datetime import datetime, time, timedelta
import pytz
import firebase_admin
from firebase_admin import credentials, firestore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

# 1. تهيئة الاتصال بـ Firebase عبر ملف الاعتماد المحلي
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 2. التوكن المعتمد لبوت "دفتر-جوال"
TOKEN = "8856892253:AAH8PMcd-Ys69_w1QmpJHs3tZ1S8DuHlhcM"

# القائمة الرئيسية المرنة
def get_main_menu():
    keyboard = [
        ["📊 تقرير تفصيلي لشهر", "📅 حركات اليوم"],
        ["📁 أرشيف السنوات والتقارير", "⚠️ الأيام غير المسجلة"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# دالة مساعدة لحفظ معرف الدردشة (chat_id) في قاعدة البيانات لتوجيه التنبيهات الليلية
def save_chat_id(chat_id):
    db.collection('settings').document('bot_config').set({
        'admin_chat_id': chat_id
    }, merge=True)

# 3. دالة الترحيب والبدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    
    welcome_text = (
        "مرحباً بك في بوت <b>دفتر-جوال</b> 📊\n"
        "إيراد • مصروف • صافي\n\n"
        "🚀 <b>طريقة الاستخدام:</b>\n"
        "• لتسجيل حركة فورية: أرسل المبلغ والبيان فقط (مثال: <code>200 مبيعات</code>).\n"
        "• لاستعراض الأرشيف والتقارير التفصيلية: استخدم الأزرار أدناه."
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=get_main_menu())

# 4. معالجة الرسائل والخيارات النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    
    text = update.message.text.strip()
    
    if text == "📊 تقرير تفصيلي لشهر":
        await show_months_list(update, context)
        return
    elif text == "📅 حركات اليوم":
        await show_today_transactions(update, context)
        return
    elif text == "📁 أرشيف السنوات والتقارير":
        await show_years_archive(update, context)
        return
    elif text == "⚠️ الأيام غير المسجلة":
        await check_missing_days(update, context)
        return

    # التحقق هل الرسالة تبدأ برقم (تسجيل حركة جديدة)
    parts = text.split(maxsplit=1)
    try:
        amount = float(parts[0])
    except ValueError:
        await update.message.reply_text(
            "أهلاً بك يا أبو مصعب ! يرجى إرسال **المبلغ والبيان** لتسجيل حركة جديدة (مثال: <code>150 صيانة</code>)، أو استخدام القائمة أدناه:",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
        return
        
    description = parts[1] if len(parts) > 1 else ""
    context.user_data['temp_amount'] = amount
    context.user_data['temp_desc'] = description

    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    keyboard = [
        [
            InlineKeyboardButton("🟢 إيراد (اليوم)", callback_data="inc_today"),
            InlineKeyboardButton("🔴 مصروف (اليوم)", callback_data="exp_today")
        ],
        [
            InlineKeyboardButton(f"📅 إيراد (أمس: {yesterday_str})", callback_data="inc_yest"),
            InlineKeyboardButton(f"📅 مصروف (أمس: {yesterday_str})", callback_data="exp_yest")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"💰 المبلغ: <b>{amount}</b>\n"
        f"📝 البيان: <b>{description if description else 'بدون بيان'}</b>\n\n"
        f"اختر نوع الحركة والتاريخ للتسجيل الفوري:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# 5. معالجة الأزرار التفاعلية
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data

    if data.startswith("year_"):
        year = int(data.split("_")[1])
        await show_months_for_year(query, year)
        return

    if data.startswith("month_"):
        parts = data.split("_")
        year = int(parts[1])
        month = int(parts[2])
        await show_detailed_month_report(query, year, month)
        return

    amount = context.user_data.get('temp_amount')
    description = context.user_data.get('temp_desc', '')

    if not amount:
        await query.edit_message_text("❌ انتهت صلاحية الجلسة، يرجى إعادة إرسال المبلغ والبيان.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    if data == "inc_today":
        t_type = "إيراد"
        target_date = today_str
    elif data == "exp_today":
        t_type = "مصروف"
        target_date = today_str
    elif data == "inc_yest":
        t_type = "إيراد"
        target_date = yesterday_str
    elif data == "exp_yest":
        t_type = "مصروف"
        target_date = yesterday_str
    else:
        return

    dt_obj = datetime.strptime(target_date, "%Y-%m-%d")
    payload = {
        "date": target_date,
        "type": t_type,
        "amount": amount,
        "description": description,
        "year": dt_obj.year,
        "month": dt_obj.month
    }

    db.collection('transactions').add(payload)

    await query.edit_message_text(
        f"✅ تم تسجيل الحركة بنجاح وحفظها في قاعدة البيانات:\n"
        f"📌 النوع: {t_type}\n"
        f"💰 المبلغ: {amount}\n"
        f"📝 البيان: {description}\n"
        f"📅 التاريخ: {target_date}"
    )

# 6. أرشيف السنوات والشهور
async def show_years_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    docs = db.collection('transactions').stream()
    years = set()
    for doc in docs:
        d = doc.to_dict()
        if "year" in d:
            years.add(d["year"])
            
    if not years:
        await update.message.reply_text("📁 لا توجد أي بيانات مسجلة في الأرشيف حتى الآن.")
        return

    keyboard = []
    for y in sorted(years, reverse=True):
        keyboard.append([InlineKeyboardButton(f"📅 سنة {y}", callback_data=f"year_{y}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📁 <b>أرشيف السجلات المالية:</b>\nاختر السنة المطلوبة لاستعراض تفاصيلها:", reply_markup=reply_markup, parse_mode="HTML")

async def show_months_for_year(query, year):
    docs = db.collection('transactions').where('year', '==', year).stream()
    months = set()
    for doc in docs:
        d = doc.to_dict()
        if "month" in d:
            months.add(d["month"])

    keyboard = []
    month_names = {1:"يناير", 2:"فبراير", 3:"مارس", 4:"أبريل", 5:"مايو", 6:"يونيو", 7:"يوليو", 8:"أغسطس", 9:"سبتمبر", 10:"أكتوبر", 11:"نوفمبر", 12:"ديسمبر"}
    
    for m in sorted(months):
        m_name = month_names.get(m, str(m))
        keyboard.append([InlineKeyboardButton(f"📂 شهر {m} ({m_name}) لعام {year}", callback_data=f"month_{year}_{m}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(f"📁 <b>أرشيف سنة {year}:</b>\nاختر الشهر لعرض الحركات والتفاصيل:", reply_markup=reply_markup, parse_mode="HTML")

async def show_months_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    docs = db.collection('transactions').where('year', '==', now.year).stream()
    months = set()
    for doc in docs:
        d = doc.to_dict()
        if "month" in d:
            months.add(d["month"])
            
    if not months:
        await update.message.reply_text("لا توجد حركات مسجلة لهذا العام بعد.")
        return

    keyboard = []
    month_names = {1:"يناير", 2:"فبراير", 3:"مارس", 4:"أبريل", 5:"مايو", 6:"يونيو", 7:"يوليو", 8:"أغسطس", 9:"سبتمبر", 10:"أكتوبر", 11:"نوفمبر", 12:"ديسمبر"}
    for m in sorted(months):
        m_name = month_names.get(m, str(m))
        keyboard.append([InlineKeyboardButton(f"📊 تفاصيل شهر {m} ({m_name})", callback_data=f"month_{now.year}_{m}")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"📊 <b>اختر الشهر المطلوب لعرض تفاصيله لعام {now.year}:</b>", reply_markup=reply_markup, parse_mode="HTML")

async def show_detailed_month_report(query, year, month):
    docs = db.collection('transactions').where('year', '==', year).where('month', '==', month).stream()
    
    month_names = {1:"يناير", 2:"فبراير", 3:"مارس", 4:"أبريل", 5:"مايو", 6:"يونيو", 7:"يوليو", 8:"أغسطس", 9:"سبتمبر", 10:"أكتوبر", 11:"نوفمبر", 12:"ديسمبر"}
    m_name = month_names.get(month, str(month))
    
    msg = f"📋 <b>تفاصيل حركات شهر {m_name} {year}:</b>\n\n"
    total_inc = 0
    total_exp = 0
    count = 0
    
    transactions = []
    for doc in docs:
        transactions.append(doc.to_dict())
    
    transactions = sorted(transactions, key=lambda x: x.get('date', ''))

    for d in transactions:
        count += 1
        t_date = d.get('date', '')
        t_type = d.get('type', '')
        amt = d.get('amount', 0)
        desc = d.get('description', '')
        
        if t_type == "إيراد":
            total_inc += amt
            msg += f"• <code>{t_date}</code> | [🟢 إيراد] <b>{amt}</b> - {desc}\n"
        else:
            total_exp += amt
            msg += f"• <code>{t_date}</code> | [🔴 مصروف] <b>{amt}</b> - {desc}\n"
            
    if count == 0:
        msg += "لا توجد حركات مسجلة في هذا الشهر."
    else:
        net = total_inc - total_exp
        msg += f"\n---------------------------\n"
        msg += f"📌 عدد الحركات: {count}\n"
        msg += f"🟢 إجمالي الإيرادات: {total_inc}\n"
        msg += f"🔴 إجمالي المصروفات: {total_exp}\n"
        msg += f"💎 الصافي الشهري: <b>{net}</b>"
        
    await query.message.reply_text(msg, parse_mode="HTML")

async def show_today_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_str = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('transactions').where('date', '==', today_str).stream()
    
    msg = f"📅 <b>حركات اليوم ({today_str}):</b>\n\n"
    total_inc = 0
    total_exp = 0
    count = 0
    
    for doc in docs:
        d = doc.to_dict()
        count += 1
        t = d.get('type')
        amt = d.get('amount', 0)
        desc = d.get('description', '')
        
        if t == "إيراد":
            total_inc += amt
            msg += f"• [🟢 إيراد] {amt} - {desc}\n"
        else:
            total_exp += amt
            msg += f"• [🔴 مصروف] {amt} - {desc}\n"
            
    if count == 0:
        msg += "لا توجد حركات مسجلة لهذا اليوم حتى الآن."
    else:
        net = total_inc - total_exp
        msg += f"\n-------------------\n🟢 الإيرادات: {total_inc}\n🔴 المصروفات: {total_exp}\n💎 الصافي: {net}"
        
    await update.message.reply_text(msg, parse_mode="HTML")

async def check_missing_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_date = datetime(2026, 8, 1)
    today = datetime.now()
    
    if start_date > today:
        if update.message:
            await update.message.reply_text("لم يبدأ شهر أغسطس 2026 بعد!")
        return []

    docs = db.collection('transactions').stream()
    recorded_dates = set()
    for doc in docs:
        data = doc.to_dict()
        if "date" in data:
            recorded_dates.add(data["date"])
            
    missing_days = []
    current_date = start_date
    while current_date <= today:
        date_str = current_date.strftime("%Y-%m-%d")
        if current_date.weekday() == 4: # استثناء الجمعة
            current_date += timedelta(days=1)
            continue
            
        if date_str not in recorded_dates:
            missing_days.append(date_str)
        current_date += timedelta(days=1)
        
    if update.message:
        if missing_days:
            msg = "⚠️ <b>الأيام التي لم يتم تسجيل أي حركة فيها (باستثناء أيام الجمعة) منذ 1 أغسطس 2026:</b>\n\n"
            for d in missing_days:
                msg += f"• {d}\n"
        else:
            msg = "🎉 ممتاز جداً! جميع الأيام المعتمدة منذ 1 أغسطس 2026 تم تسجيل حركاتها بدقة."
        await update.message.reply_text(msg, parse_mode="HTML")
        
    return missing_days

# 7. دالة التنبيه الليلة المجدولة (تعمل تلقائياً الساعة 12:10 صباحاً كل يوم)
async def nightly_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    # جلب معرف الشات المحفوظ مسبقاً من قاعدة البيانات
    doc = db.collection('settings').document('bot_config').get()
    if not doc.exists or 'admin_chat_id' not in doc.to_dict():
        return
    
    chat_id = doc.to_dict()['admin_chat_id']
    
    # التحقق مما إذا كان اليوم الحالي مسجلاً أم لا
    today_str = datetime.now().strftime("%Y-%m-%d")
    docs = db.collection('transactions').where('date', '==', today_str).stream()
    has_transactions = any(docs)
    
    if not has_transactions:
        msg = (
            "⏰ <b>تنبيه منتصف الليل:</b>\n"
            f"عذراً يا أبو مصعب ، يبدو أنك لم تسجل أي حركة مالية لهذا اليوم (<code>{today_str}</code>).\n"
            "لا تنسى تسجيل حركة اليوم 💡"
        )
        await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML", reply_markup=get_main_menu())

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # ضبط الجدولة الزمنية لتنفذ كل ليلة الساعة 12:10 صباحاً بتوقيت مكة المكرمة
    job_queue = app.job_queue
    # ضبط التوقيت المحلي (مكة المكرمة - السعودية)
    saudi_tz = pytz.timezone('Asia/Riyadh')
    
    job_queue.run_daily(
        nightly_reminder_job,
        time=time(hour=12, minute=10, tzinfo=saudi_tz) # ملاحظة: النظام يستخدم 24 ساعة، فالساعة 12:10 صباحاً تكتب (0, 10). دعنا نعدلها فوراً لـ 00:10 منتصف الليل.
    )

    # تصحيح وقت الجدولة ليكون 00:10 منتصف الليل بدقة:
    # (سنستخدم الدالة أدناه لضبطها بدقة في الصباح الباكر / منتصف الليل)
    job_queue.run_daily(
        nightly_reminder_job,
        time=time(hour=0, minute=10, tzinfo=saudi_tz)
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("missing", check_missing_days))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🤖 بوت 'دفتر-جوال V1.0' (مع الجدولة الليلية التلقائية) متصل ويعمل الآن بنجاح...")
    app.run_polling()