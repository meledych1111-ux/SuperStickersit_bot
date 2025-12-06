import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from fastapi import FastAPI, Request
import uvicorn
import json

# === КОНФИГУРАЦИЯ ===
BOT_TOKEN = "8062458019:AAFY6yl5Ijy-R1_hiyAc25j5dij9IjJMTWY"  # Ваш токен
WEBHOOK_URL = os.environ.get("RAILWAY_STATIC_URL", "")

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === ДАННЫЕ ЭФФЕКТОВ ===
EFFECTS = [
    {"id": "original", "name": "Оригинал", "emoji": "⚪"},
    {"id": "bw", "name": "Черно-белый", "emoji": "⚫"},
    {"id": "contrast", "name": "Контраст", "emoji": "🔆"},
    {"id": "vintage", "name": "Винтаж", "emoji": "🟤"},
    {"id": "sepia", "name": "Сепия", "emoji": "🟫"},
    {"id": "bright", "name": "Яркий", "emoji": "✨"},
]

# Хранилище выбранных эффектов (в памяти)
user_selections = {}

# === ОБРАБОТЧИКИ TELEGRAM ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик /start"""
    user = update.effective_user
    
    # Приветственное сообщение с кнопкой выбора эффектов
    keyboard = [
        [InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"👋 <b>Привет, {user.first_name}!</b>\n\n"
        f"🎬 Я — <b>Video Sticker Bot</b>\n\n"
        f"📹 <b>Как использовать:</b>\n"
        f"1. Выберите эффект кнопкой ниже\n"
        f"2. Отправьте мне видео\n"
        f"3. Получите стикер!\n\n"
        f"<i>Нажмите кнопку ниже чтобы начать:</i>",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_html(
        "❓ <b>Помощь по боту</b>\n\n"
        "<b>Доступные эффекты:</b>\n"
        + "\n".join([f"{e['emoji']} {e['name']}" for e in EFFECTS]) +
        "\n\n<b>Команды:</b>\n"
        "/start - Начало работы\n"
        "/effects - Выбрать эффект\n"
        "/help - Эта справка\n\n"
        "<i>Просто выберите эффект и отправьте видео!</i>"
    )

async def effects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /effects - показать эффекты"""
    await show_effects_keyboard(update.effective_chat.id)

async def show_effects_keyboard(chat_id: int, message_id: int = None):
    """Показать клавиатуру с эффектами"""
    # Создаем кнопки эффектов (по 2 в ряд)
    keyboard = []
    for i in range(0, len(EFFECTS), 2):
        row = []
        for effect in EFFECTS[i:i+2]:
            row.append(
                InlineKeyboardButton(
                    f"{effect['emoji']} {effect['name']}",
                    callback_data=f"select_effect_{effect['id']}"
                )
            )
        keyboard.append(row)
    
    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🎨 <b>Выберите эффект для обработки видео:</b>\n\n"
    text += "После выбора отправьте мне видео!"
    
    return text, reply_markup

# === ОБРАБОТЧИКИ CALLBACK QUERY (нажатия на кнопки) ===
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех callback кнопок"""
    query = update.callback_query
    await query.answer()  # Обязательно отвечаем на callback
    
    data = query.data
    user_id = query.from_user.id
    
    logger.info(f"Callback от пользователя {user_id}: {data}")
    
    if data == "show_effects":
        # Показать эффекты
        text, reply_markup = await show_effects_keyboard(query.message.chat.id)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    
    elif data.startswith("select_effect_"):
        # Выбор эффекта
        effect_id = data.replace("select_effect_", "")
        effect = next((e for e in EFFECTS if e["id"] == effect_id), EFFECTS[0])
        
        # Сохраняем выбор пользователя
        user_selections[user_id] = effect_id
        
        # Сообщение об успешном выборе
        await query.edit_message_text(
            f"✅ <b>Выбран эффект: {effect['emoji']} {effect['name']}</b>\n\n"
            f"Теперь отправьте мне видео для обработки!\n\n"
            f"<i>Или выберите другой эффект:</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Выбрать другой", callback_data="show_effects")
            ]])
        )
    
    elif data == "back_to_start":
        # Вернуться к началу
        await query.edit_message_text(
            "🎬 <b>Video Sticker Bot</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")
            ], [
                InlineKeyboardButton("❓ Помощь", callback_data="help")
            ]])
        )
    
    elif data == "help":
        # Показать помощь
        await query.edit_message_text(
            await help_command_text(),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")
            ]])
        )

async def help_command_text():
    """Текст помощи"""
    return (
        "❓ <b>Помощь по боту</b>\n\n"
        "<b>Как использовать:</b>\n"
        "1. Выберите эффект из списка\n"
        "2. Отправьте видео (до 20MB)\n"
        "3. Получите обработанный стикер!\n\n"
        "<b>Доступные эффекты:</b>\n" +
        "\n".join([f"{e['emoji']} {e['name']}" for e in EFFECTS]) +
        "\n\n<b>Ограничения:</b>\n"
        "• Видео до 20MB\n"
        "• Длительность до 30 сек\n"
        "• Форматы: MP4, MOV, AVI\n\n"
        "<i>Выберите эффект и отправьте видео!</i>"
    )

# === ОБРАБОТКА ВИДЕО ===
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящего видео"""
    user_id = update.effective_user.id
    video = update.message.video
    
    # Проверяем, выбрал ли пользователь эффект
    if user_id not in user_selections:
        # Если не выбрал - предлагаем выбрать
        keyboard = [
            [InlineKeyboardButton("🎨 Выбрать эффект сейчас", callback_data="show_effects")]
        ]
        
        await update.message.reply_html(
            "⚠️ <b>Сначала выберите эффект!</b>\n\n"
            "Пожалуйста, выберите эффект для обработки видео:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Получаем выбранный эффект
    effect_id = user_selections[user_id]
    effect = next((e for e in EFFECTS if e["id"] == effect_id), EFFECTS[0])
    
    # Отправляем сообщение о начале обработки
    processing_msg = await update.message.reply_html(
        f"🔄 <b>Начинаю обработку...</b>\n\n"
        f"📹 <b>Информация:</b>\n"
        f"• Размер: {video.file_size / (1024*1024):.1f}MB\n"
        f"• Длительность: {video.duration} сек\n"
        f"• Эффект: {effect['emoji']} {effect['name']}\n\n"
        f"<i>Обработка займет несколько секунд...</i>"
    )
    
    try:
        # Здесь будет обработка видео с FFmpeg
        # Пока просто имитируем обработку
        import asyncio
        await asyncio.sleep(2)  # Имитация обработки
        
        # Обновляем статус
        await processing_msg.edit_text(
            f"✅ <b>Обработка завершена!</b>\n\n"
            f"🎬 Эффект: {effect['name']}\n"
            f"⚡ Время: ~2 секунды\n\n"
            f"<i>В реальной версии здесь будет готовый стикер!</i>",
            parse_mode="HTML"
        )
        
        # Кнопка для нового видео
        keyboard = [
            [InlineKeyboardButton("🔄 Обработать еще", callback_data="show_effects")]
        ]
        
        await update.message.reply_html(
            f"🎉 <b>Готово!</b>\n\n"
            f"Стикер с эффектом <b>{effect['name']}</b> успешно создан!\n\n"
            f"<i>Хотите обработать еще видео?</i>",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки видео: {e}")
        await processing_msg.edit_text(
            "❌ <b>Произошла ошибка при обработке</b>\n\n"
            "Попробуйте другое видео или свяжитесь с поддержкой.",
            parse_mode="HTML"
        )

# === ОБРАБОТКА ТЕКСТА ===
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    text = update.message.text
    
    if text.lower() in ["привет", "hello", "hi"]:
        await update.message.reply_text("👋 Привет! Выберите эффект для обработки видео!")
    else:
        # Предлагаем выбрать эффект
        keyboard = [
            [InlineKeyboardButton("🎨 Выбрать эффект", callback_data="show_effects")]
        ]
        
        await update.message.reply_html(
            "🤖 <b>Video Sticker Bot</b>\n\n"
            "Я создаю стикеры из видео с эффектами!\n\n"
            "<b>Чтобы начать:</b>\n"
            "1. Выберите эффект\n"
            "2. Отправьте видео\n"
            "3. Получите стикер!\n\n"
            "<i>Нажмите кнопку ниже:</i>",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# === НАСТРОЙКА ПРИЛОЖЕНИЯ ===
def create_application():
    """Создание и настройка приложения Telegram"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("effects", effects_command))
    
    # Обработчик callback кнопок (ВАЖНО: должен быть перед другими хендлерами!)
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.VIDEO, handle_video))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    return application

# === FASTAPI ДЛЯ WEBHOOK ===
app = FastAPI(title="Video Sticker Bot")
telegram_app = None

@app.on_event("startup")
async def startup_event():
    """Запуск при старте сервера"""
    global telegram_app
    
    logger.info("🚀 Запускаю бота...")
    
    # Создаем приложение Telegram
    telegram_app = create_application()
    
    # Инициализируем
    await telegram_app.initialize()
    
    # Устанавливаем вебхук если есть URL
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        logger.info(f"✅ Webhook установлен: {webhook_url}")
    
    logger.info(f"🤖 Бот готов! Username: @{(await telegram_app.bot.get_me()).username}")

@app.post("/webhook")
async def webhook(request: Request):
    """Обработка вебхука от Telegram"""
    try:
        # Получаем данные
        data = await request.json()
        
        # Создаем обновление
        update = Update.de_json(data, telegram_app.bot)
        
        # Обрабатываем
        await telegram_app.process_update(update)
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}, 500

@app.get("/")
async def root():
    """Главная страница"""
    return {
        "status": "online",
        "service": "Telegram Video Sticker Bot",
        "mode": "webhook" if WEBHOOK_URL else "polling",
        "effects_count": len(EFFECTS)
    }

@app.get("/health")
async def health():
    """Health check для Railway"""
    return {"status": "healthy", "timestamp": "now"}

@app.get("/debug/users")
async def debug_users():
    """Отладка: список пользователей с выбранными эффектами"""
    return {
        "user_count": len(user_selections),
        "users": user_selections
    }

# Запуск сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Сервер запускается на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
