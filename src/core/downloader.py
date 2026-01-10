"""
Основной модуль загрузки видео
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.config import config


class VideoDownloader:
    """Класс для скачивания видео"""
    
    def __init__(self, log_callback=None):
        """
        Args:
            log_callback: Функция для логирования
        """
        self.log_callback = log_callback
        self.config = config
    
    def log(self, message: str, level: str = "info"):
        """Логирование сообщений"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level.upper()}] {message}")
    
    def check_dependencies(self) -> bool:
        """Проверка наличия необходимых утилит"""
        missing = []
        
        if not os.path.exists(self.config.n_m3u8dl_re):
            missing.append("N_m3u8DL-RE")
        
        if not os.path.exists(self.config.ffmpeg):
            missing.append("FFmpeg")
        
        if missing:
            self.log(f"Отсутствуют необходимые утилиты: {', '.join(missing)}", "error")
            self.log(f"Разместите утилиты в папке utils/", "error")
            return False
        
        return True
    
    def download_video(self, 
                      mpd_url: str,
                      referrer: str,
                      quality: str = "Авто",
                      audio_lang: str = "Авто",
                      output_filename: str = None) -> bool:
        """
        Скачивание видео
        
        Args:
            mpd_url: URL MPD файла
            referrer: Referrer для запросов
            quality: Качество видео
            audio_lang: Язык аудио
            output_filename: Имя выходного файла
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.check_dependencies():
            return False
        
        try:
            self.log(f"Начинаем скачивание видео...")
            self.log(f"MPD URL: {mpd_url}")
            self.log(f"Качество: {quality}")
            
            # Генерируем имя файла если не указано
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"video_{timestamp}.mp4"
            
            # Подготавливаем аргументы для N_m3u8DL-RE
            args = [
                self.config.n_m3u8dl_re,
                mpd_url,
                "--saveName", output_filename,
                "--saveDir", self.config.output_dir,
                "--tmpDir", self.config.temp_dir,
                "--headers", f"referer: {referrer}",
                "--checkSegmentsCount", "false"
            ]
            
            # Добавляем настройки качества
            if quality != "Авто":
                quality_map = {
                    "1080p": "1080",
                    "720p": "720", 
                    "480p": "480",
                    "360p": "360"
                }
                if quality in quality_map:
                    args.extend(["--select", f"vcodec:{quality_map[quality]}"])
            
            # Если есть ключи, добавляем их
            if hasattr(self, 'drm_keys') and self.drm_keys:
                keys_args = []
                for key in self.drm_keys:
                    keys_args.append(f"--key")
                    keys_args.append(key)
                args.extend(keys_args)
            
            self.log(f"Запуск N_m3u8DL-RE с аргументами: {' '.join(args)}")
            
            # Запускаем процесс
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            # Читаем вывод в реальном времени
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(output.strip(), "info")
            
            # Получаем код возврата
            return_code = process.poll()
            
            if return_code == 0:
                self.log(f"Видео успешно скачано: {output_filename}", "success")
                return True
            else:
                stderr = process.stderr.read()
                self.log(f"Ошибка скачивания: {stderr}", "error")
                return False
            
        except Exception as e:
            self.log(f"Исключение при скачивании: {str(e)}", "error")
            return False
    
    def cleanup_temp_files(self):
        """Очистка временных файлов"""
        if not self.config.keep_temp_files:
            try:
                import shutil
                if os.path.exists(self.config.temp_dir):
                    shutil.rmtree(self.config.temp_dir)
                    os.makedirs(self.config.temp_dir, exist_ok=True)
                    self.log("Временные файлы очищены")
            except Exception as e:
                self.log(f"Ошибка очистки временных файлов: {e}", "warning")