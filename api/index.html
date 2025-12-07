import { exec } from 'child_process';
import { promisify } from 'util';
import { createWriteStream, readFileSync, unlinkSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const execAsync = promisify(exec);
const BOT_TOKEN = process.env.BOT_TOKEN;

// Главный обработчик
export default async function handler(request, response) {
  console.log(`🔧 ${request.method} ${request.url}`);
  
  // CORS
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  // OPTIONS
  if (request.method === 'OPTIONS') {
    response.status(200).end();
    return;
  }
  
  // GET - health check
  if (request.method === 'GET') {
    // Проверяем FFmpeg
    try {
      const { stdout } = await execAsync('ffmpeg -version');
      const ffmpegVersion = stdout.split('\n')[0];
      
      response.status(200).json({
        status: 'online',
        service: 'Telegram Video Sticker Bot',
        ffmpeg: true,
        version: ffmpegVersion,
        fluid_compute: true,
        max_duration: '300 seconds'
      });
    } catch (error) {
      response.status(200).json({
        status: 'online',
        service: 'Telegram Video Sticker Bot',
        ffmpeg: false,
        error: 'FFmpeg not found'
      });
    }
    return;
  }
  
  // POST - Telegram webhook
  if (request.method === 'POST') {
    try {
      // Читаем body
      const chunks = [];
      for await (const chunk of request) {
        chunks.push(chunk);
      }
      const body = Buffer.concat(chunks).toString();
      
      if (!body.trim()) {
        response.status(200).json({ ok: true });
        return;
      }
      
      const data = JSON.parse(body);
      console.log('📨 Update ID:', data.update_id);
      
      // Обрабатываем сообщение
      if (data.message) {
        await handleMessage(data.message);
      }
      
      response.status(200).json({ ok: true });
      
    } catch (error) {
      console.error('❌ Handler error:', error);
      response.status(200).json({ ok: true });
    }
    return;
  }
  
  response.status(404).json({ error: 'Not found' });
}

// Обработка сообщений
async function handleMessage(message) {
  const chatId = message.chat.id;
  
  // Команда /start
  if (message.text === '/start') {
    await sendTelegramMessage(chatId,
      '🎬 *Video Sticker Bot*\n\n' +
      'Я превращаю видео в Telegram стикеры!\n\n' +
      '✅ *Как использовать:*\n' +
      '1. Отправьте мне видео (до 50MB)\n' +
      '2. Я скачаю его\n' +
      '3. Конвертирую в WebM 512x512\n' +
      '4. Отправлю готовый стикер!\n\n' +
      '⚡ *Fluid Compute включен*\n' +
      '• FFmpeg: ✅ доступен\n' +
      '• Время: 5 минут\n' +
      '• RAM: 1GB'
    );
  }
  
  // Обработка видео
  if (message.video) {
    const video = message.video;
    const fileId = video.file_id;
    
    try {
      // 1. Уведомляем о начале
      await sendTelegramMessage(chatId, '🔄 Получаю видео от Telegram...');
      
      // 2. Получаем URL файла
      const fileUrl = await getTelegramFileUrl(fileId);
      
      // 3. Скачиваем
      await sendTelegramMessage(chatId, '📥 Скачиваю видео...');
      const videoPath = await downloadFile(fileUrl);
      
      // 4. Конвертируем
      await sendTelegramMessage(chatId, '⚡ Конвертирую в стикер WebM...');
      const stickerPath = await convertToSticker(videoPath, 10); // 10 секунд макс
      
      // 5. Отправляем стикер
      await sendTelegramMessage(chatId, '📤 Отправляю стикер...');
      await sendTelegramSticker(chatId, stickerPath);
      
      // 6. Уведомляем об успехе
      await sendTelegramMessage(chatId, '✅ Готово! Стикер отправлен.');
      
      // 7. Очищаем временные файлы
      cleanupFiles([videoPath, stickerPath]);
      
    } catch (error) {
      console.error('❌ Video processing error:', error);
      await sendTelegramMessage(chatId, `❌ Ошибка: ${error.message}`);
    }
  }
}

// КОНВЕРТАЦИЯ В СТИКЕР С FFMPEG
async function convertToSticker(inputPath, maxDuration = 10) {
  const outputPath = join(tmpdir(), `sticker_${Date.now()}.webm`);
  
  // Команда FFmpeg для создания стикера
  const cmd = `
    ffmpeg -i "${inputPath}" \
    -t ${maxDuration} \
    -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2" \
    -c:v libvpx-vp9 \
    -b:v 500K \
    -an \
    -f webm \
    -y "${outputPath}"
  `;
  
  console.log(`🎬 FFmpeg command: ${cmd}`);
  
  try {
    const { stdout, stderr } = await execAsync(cmd, { timeout: 240000 }); // 4 минуты
    
    if (stderr && !stderr.includes('frame=')) {
      console.warn('FFmpeg warnings:', stderr);
    }
    
    console.log(`✅ Conversion successful: ${outputPath}`);
    return outputPath;
    
  } catch (error) {
    console.error('❌ FFmpeg error:', error.message);
    // Пробуем упрощенную команду
    return convertToStickerSimple(inputPath, outputPath, maxDuration);
  }
}

// Упрощенная конвертация (запасной вариант)
async function convertToStickerSimple(inputPath, outputPath, maxDuration) {
  const simpleCmd = `
    ffmpeg -i "${inputPath}" \
    -t ${maxDuration} \
    -vf "scale=512:512" \
    -c:v libvpx-vp9 \
    -an \
    "${outputPath}"
  `;
  
  console.log(`🎬 Simple FFmpeg command: ${simpleCmd}`);
  await execAsync(simpleCmd, { timeout: 180000 }); // 3 минуты
  return outputPath;
}

// Скачивание файла
async function downloadFile(url) {
  const filePath = join(tmpdir(), `video_${Date.now()}.mp4`);
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Download failed: ${response.statusText}`);
  }
  
  const writer = createWriteStream(filePath);
  response.body.pipe(writer);
  
  return new Promise((resolve, reject) => {
    writer.on('finish', () => resolve(filePath));
    writer.on('error', reject);
  });
}

// Отправка стикера в Telegram
async function sendTelegramSticker(chatId, stickerPath) {
  if (!BOT_TOKEN) {
    throw new Error('BOT_TOKEN not configured');
  }
  
  const stickerBuffer = readFileSync(stickerPath);
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendDocument`;
  
  const formData = new FormData();
  formData.append('chat_id', chatId);
  formData.append('document', new Blob([stickerBuffer]), 'sticker.webm');
  
  const response = await fetch(url, {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  if (!result.ok) {
    throw new Error(`Telegram API: ${result.description}`);
  }
  
  return result;
}

// Вспомогательные функции
async function getTelegramFileUrl(fileId) {
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/getFile?file_id=${fileId}`;
  const response = await fetch(url);
  const data = await response.json();
  
  if (!data.ok) throw new Error(`Telegram API: ${data.description}`);
  
  return `https://api.telegram.org/file/bot${BOT_TOKEN}/${data.result.file_path}`;
}

async function sendTelegramMessage(chatId, text) {
  if (!BOT_TOKEN) {
    console.log('📝 Would send:', text);
    return;
  }
  
  const url = `https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'Markdown'
    })
  });
  
  return response.json();
}

function cleanupFiles(filePaths) {
  filePaths.forEach(path => {
    try {
      unlinkSync(path);
      console.log(`🧹 Cleaned up: ${path}`);
    } catch (e) {
      console.warn(`⚠️ Could not delete ${path}:`, e.message);
    }
  });
}

// Polyfill для FormData в Node.js
class FormData {
  constructor() {
    this.boundary = `----WebKitFormBoundary${Math.random().toString(36).substr(2)}`;
    this.parts = [];
  }
  
  append(name, value, filename) {
    this.parts.push({ name, value, filename });
  }
  
  getHeaders() {
    return {
      'Content-Type': `multipart/form-data; boundary=${this.boundary}`
    };
  }
  
  getBuffer() {
    const chunks = [];
    
    this.parts.forEach(part => {
      chunks.push(`--${this.boundary}\r\n`);
      chunks.push(`Content-Disposition: form-data; name="${part.name}"`);
      
      if (part.filename) {
        chunks.push(`; filename="${part.filename}"`);
        chunks.push(`\r\nContent-Type: video/webm\r\n\r\n`);
        chunks.push(part.value);
      } else {
        chunks.push(`\r\n\r\n${part.value}`);
      }
      
      chunks.push('\r\n');
    });
    
    chunks.push(`--${this.boundary}--\r\n`);
    return Buffer.concat(chunks.map(chunk => 
      Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    ));
  }
}
