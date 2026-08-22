import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Список Telegram user_id адміністраторів через кому в .env
# Дізнатися свій id можна у бота @userinfobot
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

CAFE_NAME = os.getenv("CAFE_NAME", "Затишний куточок")
CAFE_ADDRESS = os.getenv("CAFE_ADDRESS", "вул. Прикладна, 1")
CAFE_PHONE = os.getenv("CAFE_PHONE", "+380 00 000 00 00")

# Час роботи кафе — використовується і для показу, і для перевірки бронювань.
# Формат ГГ:ХХ, обов'язково однаковий формат в обох змінних.
CAFE_OPEN_TIME = os.getenv("CAFE_OPEN_TIME", "09:00")
CAFE_CLOSE_TIME = os.getenv("CAFE_CLOSE_TIME", "23:00")
CAFE_HOURS = os.getenv("CAFE_HOURS", f"{CAFE_OPEN_TIME}–{CAFE_CLOSE_TIME}")

# Наскільки далеко наперед можна бронювати столик (у днях)
MAX_BOOKING_DAYS_AHEAD = int(os.getenv("MAX_BOOKING_DAYS_AHEAD", "90"))
