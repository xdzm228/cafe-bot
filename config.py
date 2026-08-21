import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Список Telegram user_id адміністраторів через кому в .env
# Дізнатися свій id можна у бота @userinfobot
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

CAFE_NAME = os.getenv("CAFE_NAME", "Затишний куточок")
CAFE_ADDRESS = os.getenv("CAFE_ADDRESS", "вул. Прикладна, 1")
CAFE_HOURS = os.getenv("CAFE_HOURS", "09:00–23:00")
CAFE_PHONE = os.getenv("CAFE_PHONE", "+380 00 000 00 00")
