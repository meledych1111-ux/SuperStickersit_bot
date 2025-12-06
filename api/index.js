import TelegramBot from 'node-telegram-bot-api';
import { exec } from 'child_process';
import { promisify } from 'util';
import { createWriteStream, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';

const execAsync = promisify(exec);

// Инициализация бота
const BOT_TOKEN = process.env.BOT_TOKEN;
if (!BOT_TOKEN) {
  console.error('❌ BOT_TOKEN not found in environment variables');
  process.exit(1);
}

const bot = new TelegramBot(BOT_TOKEN, { 
  polling: false,
  webHook: false
});

// Конвертация видео
async function convertVideoToSticker(inputPath, outputPath, duration = 10) {
  const cmd = `ffmpeg -i ${inputPath} -t ${duration} -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2" -c:v libvpx-vp9 -b:v 500K -an -f webm ${outputPath}`;
  
  console.log(`Running FFmpeg: ${cmd}`);
  
  try {
    const { stdout, stderr } = await execAsync(cmd, { timeout: 280000 });
    console.log('FFmpeg output:', stdout);
    if (stderr) console.log('FFmpeg warnings:', stderr);
    return true;
  } catch (error) {
    console.error('FFmpeg error:', error.message);
    throw error;
  }
}

// Скачивание файла
async function downloadFile(url, path) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to download: ${response.statusText}`);
  }
  
  const writer = createWriteStream(path);
  response.body.pipe(writer);
  
  return new Promise((resolve, reject) => {
    writer.on('finish', resolve);
    writer.on('error', reject);
  });
}

// Главный обработчик
export default async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // OPTIONS
  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }
  
  // Health check
  if (req.method === 'GET') {
    res.status(200).json({
      status: 'online',
      service: 'Telegram Video Sticker Bot',
      fluid_compute: true
    });
    return;
  }
  
  // Читаем body
  let body = '';
  req.on('data', chunk => {
    body += chunk.toString();
  });
  
  req.on('end', async () => {
    try {
      const data = JSON.parse(body);
      console.log('Received update:', JSON.stringify(data, null, 2));
      
      // Команда /start
      if (data.message?.text === '/start') {
        await bot.sendMessage(
          data.message.chat.id,
          `🎬 <b>Video Sticker Bot</b>\n\n` +
          `Я превращаю видео в Telegram стикеры!\n\n` +
          `✅ <b>Что можно:</b>\n` +
          `• Видео до 50MB\n` +
          `• Длительность до 60 сек\n\n` +
          `🚀 Просто отправьте мне видео!`,
          { parse_mode: 'HTML' }
        );
        
        res.status(200).json({ ok: true });
        return;
      }
      
      // Обработка видео
      if (data.message?.video) {
        const chatId = data.message.chat.id;
        const fileId = data.message.video.file_id;
        
        await bot.sendMessage(chatId, '🔄 Скачиваю видео...');
        
        try {
          // Получаем URL файла
          const file = await bot.getFile(fileId);
          const fileUrl = `https://api.telegram.org/file/bot${BOT_TOKEN}/${file.file_path}`;
          
          // Временные файлы
          const tempDir = '/tmp';
          const inputPath = join(tempDir, `input_${Date.now()}.mp4`);
          const outputPath = join(tempDir, `sticker_${Date.now()}.webm`);
          
          // Скачиваем
          await downloadFile(fileUrl, inputPath);
          
          // Конвертируем
          await bot.sendMessage(chatId, '⚡ Конвертирую в стикер...');
          await convertVideoToSticker(inputPath, outputPath, 10);
          
          // Читаем результат
          const stickerBuffer = readFileSync(outputPath);
          
          // Отправляем
          await bot.sendDocument(chatId, stickerBuffer, {}, {
            filename: 'sticker.webm',
            contentType: 'video/webm'
          });
          
          // Очищаем
          unlinkSync(inputPath);
          unlinkSync(outputPath);
          
          await bot.sendMessage(chatId, '✅ Готово!');
          
        } catch (error) {
          console.error('Processing error:', error);
          await bot.sendMessage(chatId, `❌ Ошибка: ${error.message}`);
        }
        
        res.status(200).json({ ok: true });
        return;
      }
      
      res.status(200).json({ ok: true });
      
    } catch (error) {
      console.error('Handler error:', error);
      res.status(500).json({ error: error.message });
    }
  });
}
