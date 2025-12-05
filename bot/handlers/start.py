from aiogram import types
from bot import dp

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "SuperStickersit Bot 2025\n\n"
        "Самый мощный стикер-бот в Telegram\n"
        "• Фото → стикер без фона + надпись + эффекты\n"
        "• Видео → 15 крутых видео-стикеров\n"
        "• Текст → неоновый стикер\n\n"
        "Команды:\n"
        "/my — твоя коллекция\n"
        "/pack — создать свой стикерпак\n"
        "/stats — топ и статистика\n"
        "/random — случайный стикер"
    )
