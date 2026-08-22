import json
import os
import aiosqlite

# Каталог з даними можна перевизначити через змінну оточення DATA_DIR
# (використовується, наприклад, коли БД монтується як Docker-том)
DATA_DIR = os.getenv("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "cafe_bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                phone TEXT,
                guests INTEGER,
                date TEXT,
                time TEXT,
                comment TEXT,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Одна розсилка опитування = одна "кампанія". Кожному конкретному
        # надісланому опитуванню (у Telegram у кожного отримувача — свій
        # унікальний poll_id) відповідає запис у poll_messages, який
        # прив'язує його до кампанії.
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS poll_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                options TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS poll_messages (
                poll_tg_id TEXT PRIMARY KEY,
                campaign_id INTEGER
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS poll_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                user_id INTEGER,
                user_display TEXT,
                option_ids TEXT,
                answered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(campaign_id, user_id)
            )
            """
        )
        await db.commit()


async def add_user(user_id: int, username: str | None, full_name: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name),
        )
        await db.commit()


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_reservation(user_id, name, phone, guests, date, time, comment):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO reservations (user_id, name, phone, guests, date, time, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, phone, guests, date, time, comment),
        )
        await db.commit()


async def get_reservations(limit: int = 15):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id, name, phone, guests, date, time, comment, status
               FROM reservations ORDER BY id DESC LIMIT ?""",
            (limit,),
        )
        return await cursor.fetchall()


async def get_reservation_dates() -> list[tuple[int, str]]:
    """Повертає (id, date) для всіх бронювань — використовується для пошуку
    прострочених записів, які можна видалити."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, date FROM reservations")
        return await cursor.fetchall()


async def delete_reservation(reservation_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM reservations WHERE id = ?", (reservation_id,))
        await db.commit()
        return cursor.rowcount > 0


async def delete_reservations_by_ids(ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"DELETE FROM reservations WHERE id IN ({placeholders})", ids
        )
        await db.commit()
        return cursor.rowcount


# ---------- Опитування ----------

async def create_poll_campaign(question: str, options: list[str]) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO poll_campaigns (question, options) VALUES (?, ?)",
            (question, json.dumps(options, ensure_ascii=False)),
        )
        await db.commit()
        return cursor.lastrowid


async def link_poll_message(poll_tg_id: str, campaign_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO poll_messages (poll_tg_id, campaign_id) VALUES (?, ?)",
            (poll_tg_id, campaign_id),
        )
        await db.commit()


async def get_campaign_id_by_poll(poll_tg_id: str) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT campaign_id FROM poll_messages WHERE poll_tg_id = ?", (poll_tg_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def save_poll_answer(campaign_id: int, user_id: int, user_display: str, option_ids: list[int]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR REPLACE INTO poll_answers (campaign_id, user_id, user_display, option_ids)
               VALUES (?, ?, ?, ?)""",
            (campaign_id, user_id, user_display, json.dumps(option_ids)),
        )
        await db.commit()


async def get_poll_campaigns(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT pc.id, pc.question, COUNT(pa.id) AS answers
               FROM poll_campaigns pc
               LEFT JOIN poll_answers pa ON pa.campaign_id = pc.id
               GROUP BY pc.id
               ORDER BY pc.id DESC
               LIMIT ?""",
            (limit,),
        )
        return await cursor.fetchall()


async def get_poll_campaign(campaign_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, question, options FROM poll_campaigns WHERE id = ?", (campaign_id,)
        )
        return await cursor.fetchone()


async def get_poll_answers(campaign_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, user_display, option_ids FROM poll_answers WHERE campaign_id = ?",
            (campaign_id,),
        )
        return await cursor.fetchall()
