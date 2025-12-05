from aiogram import types
from bot import dp, bot
from bot.db.models import get_db

@dp.message_handler(commands=["my"])
async def my_collection(message: types.Message):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stickers WHERE user_id=%s", (message.from_user.id,))
            total = cur.fetchone()['count']
            cur.execute("SELECT file_id, sticker_type FROM stickers WHERE user_id=%s ORDER BY created_at DESC LIMIT 9", (message.from_user.id,))
            rows = cur.fetchall()

    if total == 0:
        await message.answer("Коллекция пуста")
        return

    await message.answer(f"Коллекция: {total} стикеров")
    media = types.MediaGroup()
    for row in rows:
        if row['sticker_type'] == 'video':
            media.attach_video_note(row['file_id'])
        else:
            media.attach_sticker(row['file_id'])
    await bot.send_media_group(message.chat.id, media)
