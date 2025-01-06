from fastapi import FastAPI, Request
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from datetime import datetime, timedelta
import logging
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Дані
user_data = {}
available_slots = {}
booked_numbers = {}

# Налаштування для відправки електронної пошти
SMTP_SERVER = "mx1.cityhost.com.ua"
SMTP_PORT = 587
EMAIL_ADDRESS = "telegram_bot@keramika.uz.ua"
EMAIL_PASSWORD = "Kachora3pab1*r"
ADMIN_EMAILS = ["telegram_bot@keramika.uz.ua"]

TOKEN = os.getenv("BOT_TOKEN")
app = FastAPI()
bot = Bot(token=7890592508:AAGBVL2XvUewLkyDP1H9AW50d7hDa8hxom8)

# Відправка сповіщення на email
def send_email_notification(user_name, phone_number, day, slot):
    try:
        subject = "Новий запис на дизайн"
        body = (
            f"Користувач {user_name} ({phone_number}) записався на дизайн\n"
            f"Дата: {day}\nЧас: {slot.replace('_', ':')}"
        )

        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            for admin_email in ADMIN_EMAILS:
                msg["To"] = admin_email
                server.send_message(msg)

        logger.info("Сповіщення на електронну пошту відправлено.")
    except Exception as e:
        logger.error(f"Помилка при відправці сповіщення: {e}")

# Ініціалізація слотів для запису
def initialize_slots():
    today = datetime.now().date()
    start_date = today
    end_date = today + timedelta(days=7)
    blocked_days = {2, 3, 7, 8, 13, 14, 20, 21, 27, 28}

    delta = timedelta(days=1)
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_month = current_date.day

        if day_of_month in blocked_days:
            current_date += delta
            continue

        day_slots = []
        for hour in range(9, 18):
            slot_start = datetime(current_date.year, current_date.month, current_date.day, hour)
            if slot_start > datetime.now() + timedelta(hours=2):
                day_slots.append(f"{hour:02d}_00-{hour+1:02d}_00")

        if day_slots:
            available_slots[date_str] = day_slots
        current_date += delta

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("\ud83d\udcde Надіслати номер телефону", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Привіт! Натисніть кнопку нижче, щоб поділитися своїм номером телефону.", reply_markup=reply_markup)

# Обробка контакту
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone_number = contact.phone_number

    user_data[update.effective_user.id] = {
        "name": contact.first_name,
        "phone_number": phone_number,
    }

    if phone_number in booked_numbers:
        await update.message.reply_text(f"Ви вже записані на {booked_numbers[phone_number]['day']} о {booked_numbers[phone_number]['slot'].replace('_', ':')}.")
        return

    await update.message.reply_text(f"Дякую, {contact.first_name}! Вкажіть Ваше ім'я.")

# Обробка імені
async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()

    if user_id in user_data:
        user_data[user_id]["full_name"] = name
        buttons = [InlineKeyboardButton(day, callback_data=f"day:{day}") for day in available_slots]
        reply_markup = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])
        await update.message.reply_text("Оберіть зручний день для запису:", reply_markup=reply_markup)

# Вебхук обробка
@app.post("/webhook")
async def telegram_webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, bot)
    await app.bot.update_queue.put(update)
    return {"ok": True}

async def handle_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ваше повідомлення отримано!")

# Головна функція
def main():
    global app
    application = ApplicationBuilder().token(TOKEN).updater(None).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    application.add_handler(CallbackQueryHandler(handle_updates))

    initialize_slots()
    app.bot = application
    app.bot.update_queue = application.update_queue

if __name__ == "__main__":
    main()

