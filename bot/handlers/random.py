from aiogram import types
from bot import dp, bot
from bot.db.models import get_db

@dp.message_handler(commands=["random"])
async def random_cmd(message: types.Message):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT file_id, sticker_type FROM stickers WHERE user_id=%s ORDER BY RANDOM() LIMIT 1", (message.from_user.id,))
            row = cur.fetchone()
            if row:
                if row['sticker_type'] == 'video':
                    await bot.send_video_note(message.chat.id, row['file_id'])
                else:
                    await bot.send_sticker(message.chat.id, row['file_id'])
            else:
                await message.answer("Коллекция пуста")
