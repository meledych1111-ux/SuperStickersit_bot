import { createWriteStream, unlinkSync } from 'fs';
import { join } from 'path';
import { promisify } from 'util';
import { exec } from 'child_process';
import fetch from 'node-fetch';

const execAsync = promisify(exec);

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }
  
  try {
    const { videoUrl, duration = 10 } = req.body;
    
    if (!videoUrl) {
      return res.status(400).json({ error: 'videoUrl is required' });
    }
    
    // Скачиваем видео
    const tempDir = '/tmp';
    const inputPath = join(tempDir, `convert_${Date.now()}.mp4`);
    const outputPath = join(tempDir, `sticker_${Date.now()}.webm`);
    
    const response = await fetch(videoUrl);
    const writer = createWriteStream(inputPath);
    
    response.body.pipe(writer);
    
    await new Promise((resolve, reject) => {
      writer.on('finish', resolve);
      writer.on('error', reject);
    });
    
    // Конвертируем
    const cmd = `
      ffmpeg -i ${inputPath} \
      -t ${duration} \
      -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2" \
      -c:v libvpx-vp9 -b:v 500K -an \
      -f webm ${outputPath}
    `;
    
    await execAsync(cmd, { timeout: 280000 });
    
    // Читаем результат и отправляем
    const fs = await import('fs');
    const stickerData = fs.readFileSync(outputPath);
    
    // Удаляем временные файлы
    try {
      unlinkSync(inputPath);
      unlinkSync(outputPath);
    } catch (e) {}
    
    res.setHeader('Content-Type', 'video/webm');
    res.setHeader('Content-Disposition', 'attachment; filename="sticker.webm"');
    res.send(stickerData);
    
  } catch (error) {
    console.error('Convert error:', error);
    res.status(500).json({ error: error.message });
  }
}
