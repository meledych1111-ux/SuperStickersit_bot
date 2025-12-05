import uuid
from io import BytesIO
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from bot import dp
from bot.effects.image import fire_effect, neon_effect, glitch_effect
from bot.db.models import save_sticker

class PhotoState(StatesGroup):
    effect = State()
    caption = State()

effects = {"fire": fire_effect, "neon": neon_effect, "glitch": glitch_effect}

@dp.message_handler(content_types=["photo"])
async def photo_start(message: types.Message, state: FSMContext):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("FIRE", callback_data="eff_fire"),
        types.InlineKeyboardButton("NEON", callback_data="eff_neon"),
        types.InlineKeyboardButton("GLITCH", callback_data="eff_glitch")
    )
    await message.answer("Выбери эффект:", reply_markup=kb)
    path = f"/tmp/photo_{message.from_user.id}.jpg"
    await message.photo[-1].download(destination_file=path)
    await state.update_data(path=path)
    await PhotoState.effect.set()

@dp.callback_query_handler(lambda c: c.data.startswith("eff_"), state=PhotoState.effect)
async def choose_effect(call: types.CallbackQuery, state: FSMContext):
    effect = call.data.split("_")[1]
    await call.message.answer("Надпись (или пропустить):", 
                              reply_markup=types.InlineKeyboardMarkup().add(
                                  types.InlineKeyboardButton("Без текста", callback_data="no_text")))
    await state.update_data(effect=effect)
    await PhotoState.caption.set()

@dp.callback_query_handler(lambda c: c.data == "no_text", state=PhotoState.caption)
async def no_caption(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    img = Image.open(data['path'])
    result = effects[data['effect']](img, "")
    bio = BytesIO(); result.save(bio, "WEBP"); bio.seek(0)
    sent = await call.message.answer_sticker(types.InputFile(bio))
    save_sticker(call.from_user, "static", sent.sticker.file_id)
    await state.finish()

@dp.message_handler(state=PhotoState.caption)
async def with_caption(message: types.Message, state: FSMContext):
    data = await state.get_data()
    img = Image.open(data['path'])
    result = effects[data['effect']](img, message.text)
    bio = BytesIO(); result.save(bio, "WEBP"); bio.seek(0)
    sent = await message.answer_sticker(types.InputFile(bio))
    save_sticker(message.from_user, "static", sent.sticker.file_id, message.text)
    await state.finish()
