# check.py - Проверка зависимостей
import sys
import os
import subprocess
import shutil

print("=" * 60)
print("🔍 Проверка системы")
print("=" * 60)

# 1. Python
print(f"Python: {sys.version}")

# 2. FFmpeg
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    print(f"✅ FFmpeg: {ffmpeg_path}")

    # Проверяем версию
    try:
        result = subprocess.run([ffmpeg_path, "-version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   Версия: {version_line[:50]}")
    except:
        print("   ⚠️ Не удалось проверить версию")
else:
    print("❌ FFmpeg не найден!")

# 3. Проверяем aiogram
print("\n🔍 Проверяю aiogram...")
try:
    import aiogram
    print(f"✅ Aiogram: {aiogram.__version__}")

    # Проверяем основные импорты
    from aiogram import Bot, Dispatcher
    from aiogram.filters import Command
    from aiogram.types import Message
    print("✅ Все импорты работают")

except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
except Exception as e:
    print(f"❌ Другая ошибка: {e}")

# 4. Проверяем aiohttp
print("\n🔍 Проверяю aiohttp...")
try:
    import aiohttp
    print(f"✅ Aiohttp: {aiohttp.__version__}")
except ImportError:
    print("❌ Aiohttp не установлен")

# 5. Проверяем pydantic
print("\n🔍 Проверяю pydantic...")
try:
    import pydantic
    print(f"✅ Pydantic: {pydantic.__version__}")
except ImportError:
    print("❌ Pydantic не установлен")

print("\n" + "=" * 60)
print("✅ Проверка завершена")
print("=" * 60)
