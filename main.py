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
from geopy.distance import geodesic

from keep_alive import keep_alive

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# -- تم تحديث الإحداثيات هنا إلى الموقع الصحيح --
TARGET_LOCATION = (33.3129505, 44.3297042)
MAX_DISTANCE_METERS = 25
CSV_FILE = "attendance_records.csv"
LOCATION, ACTION_TYPE = range(2)


def save_record_to_csv(user_id, user_name, action, timestamp):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["UserID", "UserName", "Action", "Timestamp"])
        writer.writerow([user_id, user_name, action, timestamp])


async def start_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"أهلاً بك يا {user.first_name} في بوت الحضور والانصراف المستند إلى الموقع.\n\n"
        "استخدم الأوامر التالية:\n"
        "📍 /checkin - لبدء عملية تسجيل الحضور.\n"
        "👋 /checkout - لبدء عملية تسجيل الانصراف.\n"
        "📋 /records - لعرض سجلاتك الخاصة."
    )
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END


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
    else:
        await update.message.reply_text(
            f"❌ فشل التسجيل.\n"
            f"أنت بعيد جداً عن الموقع المسموح به. المسافة الحالية هي {distance:.2f} متر، والحد المسموح هو {MAX_DISTANCE_METERS} متر."
        )
    return ConversationHandler.END


async def records_command(update: telegram.Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        records = []
        with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)
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
    
    keep_alive()

    application.run_polling()


if __name__ == "__main__":
    main()
