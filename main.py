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
)
import os
import datetime
import csv
import io # <-- استيراد مكتبة للتعامل مع الملفات في الذاكرة
import asyncio

from keep_alive import keep_alive

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = 123456789  # <--- هام: تأكد من وضع الـ ID الخاص بك هنا
TARGET_LOCATION = (33.311317, 44.330635)
MAX_DISTANCE_METERS = 25
CSV_FILE = "attendance_records.csv"
LOCATION, ACTION_TYPE = range(2)


# --- الدالة الجديدة للمهمة المجدولة ---
async def send_file_periodically(application: Application):
    """تقوم بإرسال ملف السجلات كل 10 دقائق"""
    while True:
        await asyncio.sleep(600)
        if ADMIN_ID == 123456789:
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
        except FileNotFoundError:
            print("Periodic backup: Records file not found.")
        except Exception as e:
            print(f"Failed to send periodic backup: {e}")

async def post_init(application: Application):
    """دالة تعمل مرة واحدة بعد تشغيل البوت لبدء المهمة المجدولة"""
    asyncio.create_task(send_file_periodically(application))


# --- بقية الدوال ---
def save_record_to_csv(user_id, user_name, action, timestamp):
    file_exists = os.path.isfile(CSV_FILE)
    # استخدام utf-8-sig ليضيف العلامة التي يفهمها Excel
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["UserID", "UserName", "Action", "Timestamp"])
        writer.writerow([user_id, user_name, action, timestamp])

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
            "🆔 /myid - لعرض الـ ID الخاص بك."
        )
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END

async def location_handler(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # ... (بقية الدالة كما هي)
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

# --- دالة جديدة لتصدير سجلات اليوم ---
async def get_today_records_file(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
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
                # التحقق من أن تاريخ السجل هو تاريخ اليوم
                if row[3].startswith(today_date_str):
                    today_records.append(row)
        
        # إذا وجدت سجلات لليوم، قم بإنشاء ملف مؤقت في الذاكرة وأرسله
        if len(today_records) > 1:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(today_records)
            
            output.seek(0) # العودة لبداية الملف في الذاكرة
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


# --- بقية الأوامر (تبقى كما هي) ---
async def request_location(
    update: telegram.Update, context: ContextTypes.DEFAULT_TYPE, action: str
):
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
    await update.message.reply_text(
        "تم إلغاء العملية.", reply_markup=telegram.ReplyKeyboardRemove()
    )
    return ConversationHandler.END

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
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("records", records_command))
    # إضافة أوامر الأدمن
    application.add_handler(CommandHandler("getrecordsfile", get_records_file))
    application.add_handler(CommandHandler("gettoday", get_today_records_file)) # <-- إضافة الأمر الجديد
    application.add_handler(CommandHandler("myid", my_id_command))
    
    keep_alive()
    application.run_polling()


if __name__ == "__main__":
    main()
