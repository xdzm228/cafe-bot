import re
from datetime import datetime, date as date_cls, time as time_cls

# Приймає номери на кшталт +380501234567, 0501234567, +38 (050) 123-45-67 тощо.
# Головне — 9-15 цифр всередині, і рядок не повинен містити нічого зайвого, крім
# цифр, пробілів, дужок, дефісів та ведучого «+».
_PHONE_ALLOWED_CHARS_RE = re.compile(r"^\+?[\d\s\-\(\)]+$")


def validate_phone(text: str) -> str | None:
    """Повертає нормалізований (обрізаний по пробілах) номер, якщо він схожий
    на правильний, інакше None."""
    text = text.strip()
    if not text or not _PHONE_ALLOWED_CHARS_RE.match(text):
        return None
    digits = re.sub(r"\D", "", text)
    if not (9 <= len(digits) <= 15):
        return None
    return text


def parse_date(text: str) -> date_cls | None:
    """Парсить дату у форматі ДД.ММ.РРРР. Некоректні дати на кшталт 30.02.2026
    автоматично відхиляються — strptime сам кине ValueError."""
    text = text.strip()
    try:
        return datetime.strptime(text, "%d.%m.%Y").date()
    except ValueError:
        return None


def parse_time(text: str) -> time_cls | None:
    """Парсить час у форматі ГГ:ХХ."""
    text = text.strip()
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None
