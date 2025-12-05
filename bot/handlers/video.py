from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from bot import dp, bot
from bot.effects.video import apply_video_effect, ALL_VIDEO_EFFECTS
from bot.db.models import save_sticker
import uuid
import os

class VideoState(StatesGroup):
    waiting = State()

@dp.message_handler(content_types=["video", "video_note"])
async def video_start(message: types.Message, state: FSMContext):
    path = f"/tmp/vid_{uuid.uuid4()}.webm"
    await (message.video or message.video_note).download(destination_file=path)
    await state.update_data(path=path)

    kb = types.InlineKeyboardMarkup(row_width=3)
    buttons = [
        "1st SHAKE", "2nd ZOOM", "3rd GLITCH", "4th BOOMERANG", "5th SLOWMO",
        "6th NEON", "7th ROTATE", "8th KALEIDO", "9th RAINBOW", "10th VIBRANCE",
        "11th INVERT", "12th FIRE", "13th HOLO", "14th VHS", "15th EPIC"
    ]
    for i in range(0, len(buttons), 3):
        row = []
        for j in range(min(3, len(buttons)-i)):
            effect = ALL_VIDEO_EFFECTS[i+j]
            row.append(types.InlineKeyboardButton(buttons[i+j], callback_data=f"vfx_{effect}"))
        kb.row(*row)

    await message.answer("Выбери эффект:", reply_markup=kb)
    await VideoState.waiting.set()

@dp.callback_query_handler(lambda c: c.data.startswith("vfx_"), state=VideoState.waiting)
async def apply_effect(call: types.CallbackQuery, state: FSMContext):
    effect = call.data[4:]
    data = await state.get_data()
    result_path = apply_video_effect(data['path'], effect)
    
    sent = await call.message.answer_video_note(types.InputFile(result_path))
    save_sticker(call.from_user, "video", sent.video_note.file_id)
    
    os.remove(data['path'])
    os.remove(result_path)
    await state.finish()
    await call.answer(f"{effect.upper()} готов!")
