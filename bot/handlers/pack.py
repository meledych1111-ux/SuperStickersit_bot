# Название пака теперь с "superstickersit"
name = f"superstickersit_{message.from_user.id}_by_bot"
await bot.create_new_sticker_set(
    user_id=message.from_user.id,
    name=name,
    title="SuperStickersit Pack by @SuperStickersit_bot",
    emojis="",
    sticker_format="static",
    stickers=[types.InputSticker(file_id=r['file_id'], emoji_list=[""]) for r in rows]
)
await message.answer(f"Готово! Твой пак:\nhttps://t.me/addstickers/{name}")
