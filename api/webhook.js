import TelegramBot from 'node-telegram-bot-api';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { createWriteStream, unlinkSync } from 'fs';
import { promisify } from 'util';
import { exec } from 'child_process';
import fetch from 'node-fetch';
import FormData from 'form-data';

const execAsync = promisify(exec);
const __dirname = dirname(fileURLToPath(import.meta.url));

// Инициализация бота
const bot = new TelegramBot(process.env.BOT_TOKEN, { 
  polling: false,
  webHook: false
});

// Fluid Compute: ffmpeg уже установлен системно
async function convertVideoToSticker(inputPath, outputPath, duration = 10) {
  try {
    // Команда FFmpeg для стикера (512x512 WebM)
    const cmd = `
      ffmpeg -i ${inputPath} \
      -t ${duration} \
      -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2" \
      -c:v libvpx-vp9 -b:v 500K -an \
      -f webm ${outputPath}
    `;
    
    console.log(`Running FFmpeg: ${cmd}`);
    
    const { stdout, stderr } = await execAsync(cmd, { timeout: 280000 }); // 4:40 минуты
    
    if (stderr) console.log('FFmpeg stderr:', stderr);
    console.log('FFmpeg stdout:', stdout);
    
    return true;
  } catch (error) {
    console.error('FFmpeg conversion error:', error);
    throw error;
  }
}

async function downloadFile(url, path) {
  const response = await fetch(url);
  const writer = createWriteStream(path);
  
  response.body.pipe(writer);
  
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

export default async function handler(req, res) {
  // Устанавливаем CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // Обработка OPTIONS запроса
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  // Главный endpoint
  if (req.method === 'GET') {
    return res.status(200).json({
      service: 'Telegram Video Sticker Bot',
      status: 'online',
      fluid_compute: true,
      max_duration: '300 seconds',
      endpoints: {
        'POST /webhook': 'Telegram webhook',
        'POST /convert': 'Convert video to sticker'
      }
    });
  }
  
  try {
    const body = req.body;
    console.log('Received:', JSON.stringify(body, null, 2));
    
    // Обработка команды /start
    if (body.message?.text === '/start') {
      await bot.sendMessage(
        body.message.chat.id,
        '🎬 *Video Sticker Bot*\n\n' +
        'Я превращаю видео в Telegram стикеры!\n\n' +
        '✅ *Что можно:*\n' +
        '• Видео до 50MB\n' + 
        '• Длительность до 60 сек\n' +
        '• Форматы: MP4, MOV, AVI, MKV\n\n' +
        '🚀 Просто отправьте мне видео!\n\n' +
        '⚡ *Fluid Compute включен*\n' +
        '• 5 минут на обработку\n' +
        '• FFmpeg нативный\n' +
        '• Быстрая конвертация',
        { parse_mode: 'Markdown' }
      );
      
      return res.status(200).json({ ok: true });
    }
    
    // Обработка видео
    if (body.message?.video) {
      const chatId = body.message.chat.id;
      const video = body.message.video;
      const fileId = video.file_id;
      
      console.log(`Processing video for chat ${chatId}, file: ${fileId}`);
      
      // Сообщение о начале обработки
      await bot.sendMessage(chatId, '🔄 Скачиваю и обрабатываю видео...');
      
      try {
        // 1. Получаем URL файла от Telegram
        const file = await bot.getFile(fileId);
        const fileUrl = `https://api.telegram.org/file/bot${process.env.BOT_TOKEN}/${file.file_path}`;
        
        console.log(`Downloading from: ${fileUrl}`);
        
        // 2. Скачиваем видео во временный файл
        const tempDir = '/tmp';
        const inputPath = join(tempDir, `input_${Date.now()}.mp4`);
        const outputPath = join(tempDir, `output_${Date.now()}.webm`);
        
        await downloadFile(fileUrl, inputPath);
        console.log(`Downloaded to: ${inputPath}`);
        
        // 3. Конвертируем в стикер (Fluid Compute позволяет!)
        await bot.sendMessage(chatId, '⚡ Конвертирую в стикер WebM...');
        
        const maxDuration = Math.min(video.duration || 60, 30); // Макс 30 сек для стикера
        await convertVideoToSticker(inputPath, outputPath, maxDuration);
        
        // 4. Отправляем стикер пользователю
        await bot.sendMessage(chatId, '📤 Отправляю стикер...');
        
        // Отправляем как документ (Telegram сам определит как стикер)
        await bot.sendDocument(chatId, outputPath, {}, {
          filename: 'sticker.webm',
          contentType: 'video/webm'
        });
        
        // 5. Очищаем временные файлы
        try {
          unlinkSync(inputPath);
          unlinkSync(outputPath);
          console.log('Temporary files cleaned up');
        } catch (cleanupError) {
          console.warn('Failed to cleanup temp files:', cleanupError);
        }
        
        await bot.sendMessage(chatId, '✅ Готово! Стикер создан успешно!');
        
      } catch (processingError) {
        console.error('Video processing error:', processingError);
        await bot.sendMessage(
          chatId,
          `❌ Ошибка при обработке: ${processingError.message}\n\n` +
          'Попробуйте другое видео или сократите длительность.'
        );
      }
      
      return res.status(200).json({ ok: true });
    }
    
    // Если не обработали, возвращаем успех
    return res.status(200).json({ ok: true });
    
  } catch (error) {
    console.error('Handler error:', error);
    return res.status(500).json({ 
      ok: false, 
      error: error.message 
    });
  }
}
