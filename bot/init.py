from aiogram import Bot, Dispatcher
import os
from .db.models import init_db

bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode="HTML")
dp = Dispatcher()

init_db()
from .handlers import *
