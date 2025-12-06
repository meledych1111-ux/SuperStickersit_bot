import subprocess
import tempfile
import os
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.processed_count = 0
        self.ffmpeg_path = self._find_ffmpeg()
    
    def _find_ffmpeg(self) -> str:
        """Найти путь к FFmpeg"""
        # На Render FFmpeg установлен глобально
        possible_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "ffmpeg"
        ]
        
        for path in possible_paths:
            try:
                subprocess.run([path, "-version"], 
                             capture_output=True, 
                             check=True)
                logger.info(f"✅ FFmpeg найден: {path}")
                return path
            except:
                continue
        
        logger.error("❌ FFmpeg не найден!")
        return "ffmpeg"  # Будем надеяться что в PATH
    
    def check_ffmpeg(self) -> bool:
        """Проверить доступность FFmpeg"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    async def process_video(self, 
                          video_data: bytes, 
                          ffmpeg_filter: str,
                          max_duration: int = 10) -> bytes:
        """Обработать видео через FFmpeg"""
        
        # Создаем временные файлы
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as input_file, \
             tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_file:
            
            input_path = input_file.name
            output_path = output_file.name
            
            try:
                # Записываем входное видео
                input_file.write(video_data)
                input_file.flush()
                
                # Команда FFmpeg для обработки
                cmd = [
                    self.ffmpeg_path,
                    '-i', input_path,
                    '-t', str(min(max_duration, 10)),  # Макс 10 секунд
                    '-vf', ffmpeg_filter,
                    '-c:v', 'libx264',           # Кодек H.264
                    '-preset', 'fast',           # Быстрая обработка
                    '-crf', '28',                # Качество
                    '-pix_fmt', 'yuv420p',       # Совместимость
                    '-movflags', '+faststart',   # Быстрый старт
                    '-an',                       # Без звука
                    '-y',                        # Перезаписать
                    output_path
                ]
                
                logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")
                
                # Запускаем FFmpeg асинхронно
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logger.error(f"FFmpeg error: {error_msg}")
                    raise Exception(f"FFmpeg processing failed: {error_msg[:100]}")
                
                # Читаем результат
                with open(output_path, 'rb') as f:
                    result = f.read()
                
                self.processed_count += 1
                logger.info(f"✅ Видео обработано. Размер: {len(result)} bytes")
                
                return result
                
            finally:
                # Удаляем временные файлы
                try:
                    os.unlink(input_path)
                    os.unlink(output_path)
                except:
                    pass
    
    async def process_video_for_sticker(self, 
                                      video_data: bytes,
                                      effect: str = "original") -> bytes:
        """Специальная обработка для Telegram стикеров"""
        
        # Фильтры для стикеров
        filters = {
            "original": "scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
            "bw": "hue=s=0,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
            "contrast": "eq=contrast=1.5:brightness=0.1,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
            "vintage": "curves=all='0/0 0.5/0.9 1/1',scale=512:512:force_original_aspect_ratio=increase,crop=512:512"
        }
        
        ffmpeg_filter = filters.get(effect, filters["original"])
        
        return await self.process_video(
            video_data=video_data,
            ffmpeg_filter=ffmpeg_filter,
            max_duration=3  # Стикеры до 3 секунд
        )
    
    def get_stats(self) -> int:
        """Получить статистику"""
        return self.processed_count
    
    def test_ffmpeg(self) -> dict:
        """Протестировать FFmpeg"""
        try:
            # Проверка версии
            version_result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Простой тест конвертации
            test_result = {
                "available": version_result.returncode == 0,
                "version": version_result.stdout.split('\n')[0] if version_result.stdout else "Unknown",
                "processed_count": self.processed_count,
                "path": self.ffmpeg_path
            }
            
            return test_result
            
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "processed_count": self.processed_count
            }
