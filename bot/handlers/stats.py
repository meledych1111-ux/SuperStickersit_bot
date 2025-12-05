from aiogram import types
from bot import dp
from bot.db.models import get_db

@dp.message_handler(commands=["stats"])
async def stats(message: types.Message):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT user_id), COUNT(*) FROM stickers")
            users, total = cur.fetchone()
            cur.execute("SELECT first_name, username, COUNT(*) as c FROM stickers GROUP BY user_id, first_name, username ORDER BY c DESC LIMIT 10")
            top = cur.fetchall()

    text = f"Пользователей: <b>{users or 0}</b>\n"
    text += f"Стикеров: <b>{total or 0}</b>\n\nТОП-10:\n"
    for i, row in enumerate(top, 1):
        name = row['first_name'] or f"@{row['username']}" if row['username'] else "Аноним"
        text += f"{i}. {name} — <b>{row['c']}</b>\n"
    await message.answer(text)
