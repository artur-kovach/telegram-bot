from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
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
EMAIL_ADDRESS = "telegram_bot@keramika.uz.ua"  # Змініть на вашу електронну пошту
EMAIL_PASSWORD = "Kachora3pab1*r"  # Змініть на ваш пароль
ADMIN_EMAILS = ["telegram_bot@keramika.uz.ua"]

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
    end_date = today + timedelta(days=7)  # Доступні слоти тільки на 7 днів вперед
    blocked_days = {2, 3, 7, 8, 13, 14, 20, 21, 27, 28}  # Блоковані дні

    delta = timedelta(days=1)
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_month = current_date.day

        # Пропускаємо заблоковані дні
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
    keyboard = [[KeyboardButton("📱 Надіслати номер телефону", request_contact=True)]]
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

    # Перевірка на існуючий запис
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

# Вибір дня
async def handle_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = query.data.split(":")[1]

    if day in available_slots:
        buttons = [InlineKeyboardButton(slot, callback_data=f"slot:{day}:{slot}") for slot in available_slots[day]]
        reply_markup = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])
        await query.message.reply_text(f"Оберіть час на {day}:", reply_markup=reply_markup)

# Вибір часу
async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query.data:
        await query.message.reply_text("Сталася помилка. Спробуйте ще раз.")
        return

    try:
        _, day, slot = query.data.rsplit(":", 2)
    except ValueError:
        await query.message.reply_text("Неправильний формат даних. Спробуйте ще раз.")
        return

    user_id = query.from_user.id
    phone_number = user_data[user_id]["phone_number"]

    # Перевірка на існуючий запис
    if phone_number in booked_numbers:
        await query.message.reply_text(f"Ви вже записані на {booked_numbers[phone_number]['day']} о {booked_numbers[phone_number]['slot'].replace('_', ':')}.")
        return

    if slot in available_slots.get(day, []):
        available_slots[day].remove(slot)
        booked_numbers[phone_number] = {"day": day, "slot": slot}
        user_name = user_data[user_id].get("full_name", "Користувач")
        await query.edit_message_text(f"Ваш запис підтверджено на {day} о {slot.replace('_', ':')}.")

        # Надсилання сповіщення на електронну пошту
        send_email_notification(user_name, phone_number, day, slot)
    else:
        await query.message.reply_text("Цей слот вже зайнятий. Оберіть інший.")

# Головна функція
def main():
    TOKEN = "7890592508:AAGBVL2XvUewLkyDP1H9AW50d7hDa8hxom8"
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))
    app.add_handler(CallbackQueryHandler(handle_day_selection, pattern="^day:"))
    app.add_handler(CallbackQueryHandler(handle_slot_selection, pattern="^slot:"))

    initialize_slots()
    logger.info("Бот запущено...")

WEBHOOK_URL = "https://blog.keramika.uz.ua/webhook"  # Замість цього вставте свій URL вебхука

async def set_webhook():
    await app.bot.set_webhook(WEBHOOK_URL)

if __name__ == "__main__":
    import asyncio
    
    asyncio.run(set_webhook())
    app.run_webhook(
        listen="0.0.0.0",
        port=8000,
        url_path="/webhook",
        webhook_url=WEBHOOK_URL,
    )
