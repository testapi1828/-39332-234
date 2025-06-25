# -*- coding: utf-8 -*-
import telegram
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
    PicklePersistence,
    CallbackQueryHandler, # <-- استيراد جديد لمعالجة ضغطات الأزرار
)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup # <-- استيراد جديد للأزرار المضمنة

import os
import datetime
import csv
import io
import asyncio

from keep_alive import keep_alive

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = 641817858  # <--- هام: تأكد من وضع الـ ID الخاص بك هنا
TARGET_LOCATION = (33.311317, 44.330635)
MAX_DISTANCE_METERS = 25
CSV_FILE = "attendance_records.csv"
# تعريف حالات المحادثات
LOCATION, ACTION_TYPE, SELECT_USER_REMOTE = range(3)


# --- دوال مساعدة ---
def get_all_users_from_csv():
    """تقرأ ملف السجلات وتعيد قاموساً بأسماء وأرقام المستخدمين الفريدين"""
    users = {}
    try:
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8-sig') as infile:
            reader = csv.reader(infile)
            header = next(reader)
            for row in reader:
                user_id, user_name = row[0], row[1]
                if user_id not in users:
                    users[user_id] = user_name
    except FileNotFoundError:
        return {} # إرجاع قاموس فارغ إذا لم يكن الملف موجوداً
    return users

def save_record_to_csv(user_id, user_name, action, timestamp):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["UserID", "UserName", "Action", "Timestamp"])
        writer.writerow([user_id, user_name, action, timestamp])


# --- دوال المهام المجدولة والأوامر الرئيسية (تبقى كما هي) ---
# ... (دوال start_command, location_handler, records_command, الخ... تبقى كما هي بالضبط) ...
# (لتجنب الإطالة، لم أكرر الدوال التي لم تتغير. الرجاء نسخها من الكود السابق أو استخدام هذا الكود الكامل أدناه)

# --- الكود الكامل للدوال التي لم تتغير ---
async def send_file_periodically(application: Application):
    """تقوم بإرسال ملف السجلات كل 10 دقائق"""
    while True:
        await asyncio.sleep(600)
        if ADMIN_ID == 641817858:
            print("ADMIN_ID has not been set. Skipping periodic file send.")
            continue
        try:
            if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
                print(f"Sending periodic backup to ADMIN_ID: {ADMIN_ID}")
                await application.bot.send_document(
                    chat_id=ADMIN_ID,
                    document=open(CSV_FILE, 'rb'),
                    caption=f"نسخة احتياطية تلقائية للسجلات - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        except Exception as e:
            print(f"Failed to send periodic backup: {e}")

async def post_init(application: Application):
    asyncio.create_task(send_file_periodically(application))

async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"أهلاً بك يا {user.first_name} في بوت الحضور والانصراف.\n\n"
        "استخدم الأوامر التالية:\n"
        "📍 /checkin - لتسجيل الحضور.\n"
        "👋 /checkout - لتسجيل الانصراف.\n"
        "📋 /records - لعرض سجلاتك الخاصة."
    )
    if user.id == ADMIN_ID:
        welcome_message += (
            "\n\n--- أوامر الأدمن ---\n"
            "📁 /getrecordsfile - للحصول على ملف السجلات الكامل.\n"
            "📅 /gettoday - للحصول على ملف سجلات اليوم فقط.\n"
            " remotecheckin/ - لتسجيل حضور لموظف عن بعد.\n"
            "🆔 /myid - لعرض الـ ID الخاص بك."
        )
    await update.message.reply_text(welcome_message)
    # The return value of states is not needed here as it's not part of a conversation
    # return ConversationHandler.END 

async def location_handler(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_location = update.message.location
    action = context.user_data.get("action", "غير محدد")
    distance = geodesic(
        (user_location.latitude, user_location.longitude), TARGET_LOCATION
    ).meters
    await update.message.reply_text(
        "جاري التحقق من موقعك...", reply_markup=telegram.ReplyKeyboardRemove()
    )
    if distance <= MAX_DISTANCE_METERS:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_record_to_csv(user.id, user.first_name, action, current_time)
        await update.message.reply_text(
            f"✅ تم تسجيل {action} بنجاح!\n"
            f"أنت على بعد {distance:.2f} متر من الموقع المحدد."
        )
        try:
            if ADMIN_ID != 123456789:
                notification_text = f"🔔 تنبيه: قام المستخدم {user.first_name} ({user.id}) بتسجيل '{action}'."
                await context.bot.send_message(chat_id=ADMIN_ID, text=notification_text)
        except Exception as e:
            print(f"Failed to send notification to admin: {e}")
    else:
        await update.message.reply_text(
            f"❌ فشل التسجيل.\n"
            f"أنت بعيد جداً عن الموقع المسموح به. المسافة الحالية هي {distance:.2f} متر، والحد المسموح هو {MAX_DISTANCE_METERS} متر."
        )
    return ConversationHandler.END


# --- أوامر الأدمن ---
async def get_records_file(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو)
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للأدمن فقط.")
        return
    try:
        await context.bot.send_document(chat_id=user.id, document=open(CSV_FILE, 'rb'))
    except FileNotFoundError:
        await update.message.reply_text("ملف السجلات فارغ حالياً أو لم يتم إنشاؤه بعد.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء إرسال الملف: {e}")

async def get_today_records_file(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو)
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للأدمن فقط.")
        return
    try:
        today_date_str = datetime.date.today().isoformat()
        today_records = []
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8-sig') as infile:
            reader = csv.reader(infile)
            header = next(reader)
            today_records.append(header)
            for row in reader:
                if row[3].startswith(today_date_str):
                    today_records.append(row)
        if len(today_records) > 1:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(today_records)
            output.seek(0)
            output_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
            filename = f"attendance_{today_date_str}.csv"
            await context.bot.send_document(chat_id=user.id, document=output_bytes, filename=filename)
        else:
            await update.message.reply_text("لم يتم العثور على أي سجلات لليوم الحالي.")
    except FileNotFoundError:
        await update.message.reply_text("ملف السجلات الرئيسي غير موجود.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ: {e}")

async def my_id_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"الـ ID الخاص بك هو:\n`{user_id}`\n\nقم بنسخ هذا الرقم ووضعه في متغير `ADMIN_ID` في الكود.", parse_mode='MarkdownV2')


# --- دوال تسجيل الحضور عن بعد (الميزة الجديدة) ---
async def remote_checkin_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ محادثة تسجيل الحضور عن بعد بعرض قائمة المستخدمين"""
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للأدمن فقط.")
        return ConversationHandler.END

    all_users = get_all_users_from_csv()
    if not all_users:
        await update.message.reply_text("لا يوجد مستخدمون مسجلون في السجلات بعد.")
        return ConversationHandler.END

    # تخزين قائمة المستخدمين في ذاكرة المحادثة للوصول إليها لاحقاً
    context.user_data['all_users'] = all_users

    keyboard = []
    for user_id, user_name in all_users.items():
        # كل زر يحمل اسم المستخدم، وقيمته الخفية (callback_data) هي رقم الـ ID
        button = [InlineKeyboardButton(user_name, callback_data=user_id)]
        keyboard.append(button)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("الرجاء اختيار الموظف لتسجيل حضوره عن بعد:", reply_markup=reply_markup)
    
    return SELECT_USER_REMOTE

async def remote_checkin_button_handler(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعالج الضغط على زر اسم المستخدم"""
    query = update.callback_query
    await query.answer() # لإزالة علامة التحميل من الزر

    selected_user_id = query.data
    all_users = context.user_data.get('all_users', {})
    selected_user_name = all_users.get(selected_user_id, "Unknown")
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # تسجيل الحضور مع ملاحظة "عن بعد"
    save_record_to_csv(selected_user_id, selected_user_name, 'حضور (عن بعد)', current_time)

    await query.edit_message_text(text=f"✅ تم تسجيل حضور (عن بعد) للمستخدم: {selected_user_name}")
    
    return ConversationHandler.END


# --- بقية الدوال (تبقى كما هي) ---
async def request_location(
    update: telegram.Update, context: ContextTypes.DEFAULT_TYPE, action: str
):
    # ... (الكود كما هو)
    context.user_data["action"] = action
    keyboard = [[telegram.KeyboardButton("📍 مشاركة الموقع الحالي", request_location=True)]]
    reply_markup = telegram.ReplyKeyboardMarkup(
        keyboard, resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(
        f"لتسجيل {action}، يرجى مشاركة موقعك بالضغط على الزر أدناه.",
        reply_markup=reply_markup,
    )
    return LOCATION

async def checkin_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    return await request_location(update, context, "حضور")

async def checkout_start(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    return await request_location(update, context, "انصراف")

async def records_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو)
    user_id = update.effective_user.id
    try:
        records = []
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            header = next(reader)
            for row in reader:
                if int(row[0]) == user_id:
                    records.append(f"- {row[2]}: {row[3]}")
        if not records:
            await update.message.reply_text("لم يتم العثور على أي سجلات لك.")
            return
        response_text = f"📋 سجلاتك:\n\n" + "\n".join(records)
        await update.message.reply_text(response_text)
    except FileNotFoundError:
        await update.message.reply_text("لا توجد سجلات حتى الآن.")

async def cancel(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (الكود كما هو)
    await update.message.reply_text(
        "تم إلغاء العملية.", reply_markup=telegram.ReplyKeyboardRemove()
    )
    try:
        await context.callback_query.edit_message_text(text="تم الإلغاء.")
    except:
        pass
    return ConversationHandler.END


# --- الدالة الرئيسية (Main) ---
def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على رمز التليجرام. تأكد من إضافته في Secrets.")
        return

    persistence = PicklePersistence(filepath="bot_persistence")

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )
    
    print("Bot is starting...")
    
    # معالج محادثة الحضور والانصراف العادي
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("checkin", checkin_start),
            CommandHandler("checkout", checkout_start),
        ],
        states={
            LOCATION: [MessageHandler(filters.LOCATION, location_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        persistent=True,
        name="attendance_conversation",
    )

    # معالج محادثة تسجيل الحضور عن بعد (للأدمن)
    remote_checkin_conv = ConversationHandler(
        entry_points=[CommandHandler("remotecheckin", remote_checkin_start)],
        states={
            SELECT_USER_REMOTE: [CallbackQueryHandler(remote_checkin_button_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        persistent=True,
        name="remote_checkin_conversation"
    )
    
    # إضافة كل المعالجات للتطبيق
    application.add_handler(conv_handler)
    application.add_handler(remote_checkin_conv) # <-- إضافة معالج الميزة الجديدة

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("records", records_command))
    
    # إضافة أوامر الأدمن
    application.add_handler(CommandHandler("getrecordsfile", get_records_file))
    application.add_handler(CommandHandler("gettoday", get_today_records_file))
    application.add_handler(CommandHandler("myid", my_id_command))
    
    keep_alive()
    application.run_polling()


if __name__ == "__main__":
    main()
