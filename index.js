// В начало файла добавьте константы для GIF
const SUPPORTED_FORMATS = {
  video: ['mp4', 'mov', 'mpeg', 'avi', 'mkv', 'webm'],
  gif: ['gif'],
  document: ['mp4', 'mov', 'gif', 'webm']
};

// Обновите функцию processVideo:
async function processVideo(chatId, message) {
  try {
    const startTime = Date.now();
    
    // Определяем тип контента
    let fileId, fileSize, mimeType, isGif = false;
    
    if (message.video) {
      fileId = message.video.file_id;
      fileSize = message.video.file_size;
      mimeType = message.video.mime_type || 'video/mp4';
    } 
    else if (message.document) {
      fileId = message.document.file_id;
      fileSize = message.document.file_size;
      mimeType = message.document.mime_type;
      
      // Проверяем GIF
      const fileName = message.document.file_name || '';
      const ext = path.extname(fileName).toLowerCase().slice(1);
      
      if (mimeType === 'image/gif' || ext === 'gif') {
        isGif = true;
        await sendTelegramMessage(chatId, 
          `🎭 *Получил GIF!*\n\n` +
          `GIF будут конвертированы в видео-стикеры.\n` +
          `_Обработка может занять 5-12 секунд..._`
        );
      }
    }
    else if (message.animation) {
      fileId = message.animation.file_id;
      fileSize = message.animation.file_size;
      isGif = true; // Анимации в Telegram часто GIF
      await sendTelegramMessage(chatId,
        `🎬 *Получил анимацию!*\n\n` +
        `Конвертирую в видео-стикер...\n` +
        `_Ожидайте 5-10 секунд_`
      );
    }
    
    // Проверка размера
    if (!fileSize) {
      await sendTelegramMessage(chatId,
        `❌ *Не могу определить размер файла*\n` +
        `Попробуйте отправить как документ.`
      );
      return;
    }
    
    const sizeMB = (fileSize / 1024 / 1024).toFixed(2);
    
    // Разные лимиты для GIF и видео
    const maxSize = isGif ? 8 * 1024 * 1024 : MAX_VIDEO_SIZE; // 8MB для GIF
    
    if (fileSize > maxSize) {
      await sendTelegramMessage(chatId,
        `❌ *${isGif ? 'GIF' : 'Видео'} слишком ${isGif ? 'большой' : 'большое'}!*\n\n` +
        `Максимальный размер ${isGif ? 'GIF' : 'видео'}: *${maxSize / 1024 / 1024}MB*\n` +
        `Ваш файл: *${sizeMB}MB*\n\n` +
        `*Что делать:*\n` +
        `${isGif ? '• Используйте онлайн-сжатие GIF\n' : '• Сожмите видео до 10MB\n'}` +
        `• Отправьте более короткий файл\n` +
        `• Для GIF попробуйте конвертировать в MP4`
      );
      return;
    }
    
    // Уведомление о начале обработки
    if (!isGif) {
      await sendTelegramMessage(chatId,
        `✅ *Получил ${isGif ? 'GIF' : 'видео'}!* (${sizeMB}MB)\n\n` +
        `_Начинаю обработку... (${isGif ? '5-12' : '5-10'} секунд)_`
      );
    }
    
    // 1. Получаем URL
    const fileUrl = await getFileUrl(fileId);
    
    // 2. Скачиваем
    const inputExt = isGif ? 'gif' : 'mp4';
    const inputPath = path.join(os.tmpdir(), `input_${Date.now()}.${inputExt}`);
    await downloadFile(fileUrl, inputPath);
    
    // 3. Конвертируем с учетом типа
    await sendTelegramMessage(chatId, `⚡ Конвертирую ${isGif ? 'GIF' : 'видео'} в стикер...`);
    const outputPath = path.join(os.tmpdir(), `sticker_${Date.now()}.webm`);
    
    // Разные команды FFmpeg для GIF и видео
    let ffmpegCmd;
    
    if (isGif) {
      // Для GIF - оптимизированная команда
      ffmpegCmd = `timeout 15 ffmpeg -i "${inputPath}" \
        -t ${MAX_DURATION} \
        -vf "fps=15,scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:-1:-1:color=black" \
        -c:v libvpx-vp9 \
        -crf 35 \
        -b:v 300k \
        -an \
        -f webm \
        -y "${outputPath}" 2>&1`;
    } else {
      // Для видео
      ffmpegCmd = `timeout 20 ffmpeg -i "${inputPath}" \
        -t ${MAX_DURATION} \
        -vf "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:-1:-1:color=black" \
        -c:v libvpx-vp9 \
        -crf 32 \
        -b:v 400k \
        -an \
        -f webm \
        -y "${outputPath}" 2>&1`;
    }
    
    console.log(`🎬 Processing ${isGif ? 'GIF' : 'video'} ${sizeMB}MB`);
    
    try {
      const { stdout, stderr } = await execAsync(ffmpegCmd, { timeout: isGif ? 20000 : 25000 });
    } catch (ffmpegError) {
      console.error('FFmpeg error:', ffmpegError.message);
      
      if (ffmpegError.message.includes('timeout')) {
        await sendTelegramMessage(chatId,
          `❌ *Таймаут обработки!*\n\n` +
          `${isGif ? 'GIF' : 'Видео'} слишком сложное.\n\n` +
          `*Попробуйте:*\n` +
          `• ${isGif ? 'Более простой GIF' : 'Более простое видео'}\n` +
          `• Меньший размер (${isGif ? '1-3' : '2-5'}MB)\n` +
          `${isGif ? '• Конвертируйте GIF в MP4' : '• Формат MP4 с H.264'}`
        );
        fs.unlinkSync(inputPath);
        return;
      }
      
      // Пробуем простую команду
      await sendTelegramMessage(chatId, '⚠️ Пробую альтернативную конвертацию...');
      const simpleCmd = `timeout 15 ffmpeg -i "${inputPath}" \
        -t ${MAX_DURATION} \
        -vf "scale=512:512" \
        -c:v libvpx-vp9 \
        -an \
        -y "${outputPath}"`;
      await execAsync(simpleCmd, { timeout: 18000 });
    }
    
    // 4. Проверяем результат
    if (!fs.existsSync(outputPath)) {
      throw new Error('FFmpeg не создал файл');
    }
    
    const stats = fs.statSync(outputPath);
    if (stats.size === 0) {
      throw new Error('Пустой выходной файл');
    }
    
    // 5. Отправляем стикер
    await sendTelegramMessage(chatId, '📤 Отправляю стикер...');
    await sendVideoAsSticker(chatId, outputPath);
    
    // 6. Статистика
    const processTime = ((Date.now() - startTime) / 1000).toFixed(1);
    const outputSizeKB = (stats.size / 1024).toFixed(1);
    
    await sendTelegramMessage(chatId,
      `✅ *Готово!*\n\n` +
      `🎬 ${isGif ? 'GIF' : 'Видео'} → стикер успешно!\n` +
      `⏱ Время обработки: ${processTime} сек\n` +
      `📏 Размер стикера: ${outputSizeKB}KB\n` +
      `📐 Разрешение: 512x512 пикселей\n` +
      `⏳ Длительность: ${MAX_DURATION} сек\n\n` +
      `${isGif ? '🎭' : '🎬'} Можете отправлять следующий файл!`
    );
    
    // 7. Очистка
    fs.unlinkSync(inputPath);
    fs.unlinkSync(outputPath);
    
  } catch (error) {
    console.error('❌ Processing error:', error);
    
    let errorMessage = `❌ Ошибка обработки ${isGif ? 'GIF' : 'видео'}`;
    let advice = '';
    
    if (error.message.includes('Invalid data') || error.message.includes('GIF')) {
      errorMessage = '🎭 Ошибка обработки GIF';
      advice = 'GIF может быть слишком сложным. Попробуйте:\n• Более простой GIF\n• Конвертировать в MP4\n• Уменьшить количество кадров';
    }
    
    await sendTelegramMessage(chatId,
      `${errorMessage}\n\n` +
      `${advice || 'Попробуйте файл поменьше или другой формат.'}\n\n` +
      `*Рекомендации для ${isGif ? 'GIF' : 'видео'}:*\n` +
      `• Макс. размер: ${isGif ? '8MB' : '10MB'}\n` +
      `${isGif ? '• Идеальный размер: 1-3MB' : '• Идеальный размер: 2-5MB'}\n` +
      `• Если ошибка повторяется: /help`
    );
  }
}

// Обновите команду /help:
async function handleMessage(message) {
  // ... предыдущий код ...
  
  if (text.startsWith('/help')) {
    await sendTelegramMessage(chatId,
      `🆘 *Помощь*\n\n` +
      `*Поддерживаемые форматы:*\n` +
      `🎥 *Видео:*\n` +
      `• MP4 (рекомендуется, до 10MB)\n` +
      `• MOV (до 10MB)\n` +
      `• AVI (может не работать)\n\n` +
      `🎭 *GIF/анимации:*\n` +
      `• GIF (до 8MB)\n` +
      `• Telegram анимации (до 8MB)\n\n` +
      `*Лимиты:*\n` +
      `📏 Видео: до 10MB\n` +
      `🎭 GIF: до 8MB\n` +
      `⏳ Длительность стикера: 5 сек\n` +
      `⚡ Время обработки: 5-15 сек\n\n` +
      `*Оптимальные параметры:*\n` +
      `• Видео: MP4, 2-5MB, H.264\n` +
      `• GIF: до 3MB, до 30 кадров/сек\n\n` +
      `*Команды:*\n` +
      `/start - информация\n` +
      `/formats - поддерживаемые форматы\n` +
      `/limits - ограничения\n` +
      `/status - статус сервера`
    );
  }
  
  else if (text.startsWith('/formats')) {
    await sendTelegramMessage(chatId,
      `📁 *Поддерживаемые форматы*\n\n` +
      `✅ *Видео (до 10MB):*\n` +
      `• MP4 (рекомендуется)\n` +
      `• MOV\n` +
      `• WebM\n` +
      `• AVI (не гарантировано)\n\n` +
      `✅ *GIF/анимации (до 8MB):*\n` +
      `• GIF (статичные и анимированные)\n` +
      `• Telegram анимации\n\n` +
      `❌ *Не поддерживаются:*\n` +
      `• MKV (конвертируйте в MP4)\n` +
      `• FLV\n` +
      `• Видео больше 10MB\n` +
      `• GIF больше 8MB\n\n` +
      `*Совет:* Используйте MP4 для лучшей совместимости!`
    );
  }
  
  // ... остальной код ...
}
