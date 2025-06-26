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
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

import os
import datetime
import csv
import asyncio
from geopy.distance import geodesic
from zoneinfo import ZoneInfo # <-- استيراد مكتبة التوقيت الزمني

from keep_alive import keep_alive

# --- الإعدادات الرئيسية ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = 641817858 # <-- تم وضع الـ ID الخاص بك
TARGET_LOCATION = (33.311317, 44.330635)
MAX_DISTANCE_METERS = 25
CSV_FILE = "attendance_records.csv"
# تحديد التوقيت الزمني لبغداد
BAGHDAD_TZ = ZoneInfo("Asia/Baghdad")
LOCATION = 0


# --- دوال مساعدة ---
def save_record_to_csv(user_id, user_name, action, timestamp):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["UserID", "UserName", "Action", "Timestamp"])
        writer.writerow([user_id, user_name, action, timestamp])


# --- دوال المهام ---
async def send_file_periodically(application: Application):
    while True:
        await asyncio.sleep(14400)
        if ADMIN_ID == 123456789: # Kept placeholder here for safety
            print("ADMIN_ID placeholder is still in use. Skipping periodic file send.")
            continue
        try:
            if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
                print(f"Sending periodic backup to ADMIN_ID: {ADMIN_ID}")
                # استخدام توقيت بغداد في اسم الملف
                caption_time = datetime.datetime.now(BAGHDAD_TZ).strftime('%Y-%m-%d %H:%M:%S')
                with open(CSV_FILE, 'rb') as doc:
                    await application.bot.send_document(
                        chat_id=ADMIN_ID,
                        document=doc,
                        caption=f"نسخة احتياطية تلقائية للسجلات - {caption_time}"
                    )
        except Exception as e:
            print(f"Failed to send periodic backup: {e}")

async def post_init(application: Application):
    asyncio.create_task(send_file_periodically(application))


# --- دوال الأوامر الرئيسية ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "📁 /getrecordsfile - للحصول على ملف السجلات.\n"
            "🆔 /myid - لعرض الـ ID الخاص بك."
        )
    await update.message.reply_text(welcome_message)
    return ConversationHandler.END

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_origin:
        await update.message.reply_text("❌ لا يمكن تسجيل الحضور باستخدام موقع معاد توجيهه. يرجى إرسال موقعك الحالي مباشرة.")
        return ConversationHandler.END

    user = update.effective_user
    user_location = update.message.location
    action = context.user_data.get("action", "غير محدد")
    if not action or action == "غير محدد":
        await update.message.reply_text("حدث خطأ، يرجى البدء من جديد باستخدام /checkin أو /checkout.")
        return ConversationHandler.END
        
    distance = geodesic((user_location.latitude, user_location.longitude), TARGET_LOCATION).meters
    await update.message.reply_text("جاري التحقق من موقعك...", reply_markup=ReplyKeyboardRemove())
    
    if distance <= MAX_DISTANCE_METERS:
        # استخدام توقيت بغداد عند تسجيل الوقت
        current_time = datetime.datetime.now(BAGHDAD_TZ).strftime("%Y-%m-%d %H:%M:%S")
        save_record_to_csv(user.id, user.first_name, action, current_time)
        await update.message.reply_text(f"✅ تم تسجيل {action} بنجاح!\nأنت على بعد {distance:.2f} متر من الموقع المحدد.")
        try:
            notification_text = f"🔔 تنبيه: قام المستخدم {user.first_name} ({user.id}) بتسجيل '{action}'."
            await context.bot.send_message(chat_id=ADMIN_ID, text=notification_text)
        except Exception as e:
            print(f"Failed to send notification to admin: {e}")
    else:
        await update.message.reply_text(f"❌ فشل التسجيل.\nأنت بعيد جداً عن الموقع المسموح به. المسافة الحالية هي {distance:.2f} متر، والحد المسموح هو {MAX_DISTANCE_METERS} متر.")
    
    return ConversationHandler.END

async def request_location(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    context.user_data["action"] = action
    keyboard = [[KeyboardButton("📍 مشاركة الموقع الحالي", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(f"لتسجيل {action}، يرجى مشاركة موقعك بالضغط على الزر أدناه.", reply_markup=reply_markup)
    return LOCATION

async def checkin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await request_location(update, context, "حضور")

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await request_location(update, context, "انصراف")

async def get_records_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("عذراً، هذا الأمر مخصص للأدمن فقط.")
        return
    try:
        with open(CSV_FILE, 'rb') as doc:
            await context.bot.send_document(chat_id=user.id, document=doc)
    except FileNotFoundError:
        await update.message.reply_text("ملف السجلات فارغ حالياً أو لم يتم إنشاؤه بعد.")
    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء إرسال الملف: {e}")

async def records_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        records = []
        with open(CSV_FILE, mode='r', newline='', encoding='utf-8-sig') as file:
            reader = csv.reader(file)
            try:
                header = next(reader)
                for row in reader:
                    if int(row[0]) == user_id:
                        records.append(f"- {row[2]}: {row[3]}")
            except StopIteration:
                pass
        if not records:
            await update.message.reply_text("لم يتم العثور على أي سجلات لك.")
            return
        response_text = f"📋 سجلاتك:\n\n" + "\n".join(records)
        await update.message.reply_text(response_text)
    except FileNotFoundError:
        await update.message.reply_text("لا توجد سجلات حتى الآن.")

async def my_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"الـ ID الخاص بك هو:\n`{user_id}`\n\nهذا هو الرقم الذي يجب وضعه في متغير `ADMIN_ID`.", parse_mode='MarkdownV2')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.", reply_markup=ReplyKeyboardRemove())
    if update.callback_query:
        await update.callback_query.edit_message_text(text="تم الإلغاء.")
    return ConversationHandler.END

def main():
    if not TELEGRAM_TOKEN:
        print("خطأ: لم يتم العثور على رمز التليجرام.")
        return
    persistence = PicklePersistence(filepath="bot_persistence")
    application = (Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).post_init(post_init).build())
    print("Bot is starting...")

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("checkin", checkin_start),
            CommandHandler("checkout", checkout_start),
        ],
        states={
            LOCATION: [MessageHandler(filters.LOCATION, location_handler)],
        },
        fallbacks=[CommandHandler("start", start_command), CommandHandler("cancel", cancel)],
        persistent=True,
        name="attendance_conversation",
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("records", records_command))
    application.add_handler(CommandHandler("getrecordsfile", get_records_file))
    application.add_handler(CommandHandler("myid", my_id_command))
    
    keep_alive()
    application.run_polling()

if __name__ == "__main__":
    main()
