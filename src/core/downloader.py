"""
Основной модуль загрузки видео
"""
import os
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import shutil

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
            self.log(f"Не найден: {self.config.n_m3u8dl_re}", "error")
        
        if not os.path.exists(self.config.ffmpeg):
            missing.append("FFmpeg")
            self.log(f"Не найден: {self.config.ffmpeg}", "warning")
        
        if missing:
            self.log(f"Отсутствуют необходимые утилиты: {', '.join(missing)}", "error")
            return False
        
        return True
    
    def run_command(self, args: List[str]) -> Tuple[bool, str]:
        """Запуск команды и получение результата"""
        try:
            self.log(f"Запуск команды: {' '.join(args[:8])}...")
            
            # Создаем процесс с перенаправлением stdin для автоматического выбора
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,  # Важно: передаем stdin для автоматического выбора
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Собираем весь вывод
            stdout_lines = []
            stderr_lines = []
            
            # Если программа ожидает ввода (выбор потоков), отправляем Enter для подтверждения
            try:
                # Даем программе немного времени для запуска
                import time
                time.sleep(1)
                
                # Отправляем Enter для подтверждения выбора по умолчанию
                process.stdin.write('\n')
                process.stdin.flush()
            except:
                pass  # Если stdin недоступен, продолжаем
            
            # Читаем вывод в реальном времени
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    output = output.strip()
                    if output:
                        self.log(output)
                        stdout_lines.append(output)
            
            # Получаем остальной вывод
            stdout, stderr = process.communicate()
            
            if stdout:
                for line in stdout.strip().split('\n'):
                    if line:
                        self.log(line)
                        stdout_lines.append(line)
            
            if stderr:
                for line in stderr.strip().split('\n'):
                    if line:
                        self.log(f"Ошибка: {line}", "warning")
                        stderr_lines.append(line)
            
            return_code = process.poll()
            
            full_output = "\n".join(stdout_lines + stderr_lines)
            
            if return_code == 0:
                return True, full_output
            else:
                self.log(f"Код возврата: {return_code}", "error")
                return False, full_output
            
        except Exception as e:
            self.log(f"Исключение при запуске команды: {str(e)}", "error")
            return False, str(e)
    
    def download_video(self, 
                      mpd_url: str,
                      referrer: str,
                      quality: str = "Авто",
                      audio_lang: str = "Авто",
                      drm_keys: List[str] = None,
                      output_filename: str = None) -> bool:
        """
        Скачивание видео
        
        Args:
            mpd_url: URL MPD файла
            referrer: Referrer для запросов
            quality: Качество видео
            audio_lang: Язык аудио
            drm_keys: Список ключей DRM
            output_filename: Имя выходного файла
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.check_dependencies():
            return False
        
        try:
            self.log("=" * 60)
            self.log("НАЧАЛО СКАЧИВАНИЯ ВИДЕО")
            self.log(f"MPD URL: {mpd_url}")
            self.log(f"Качество: {quality}")
            self.log(f"Ключей DRM: {len(drm_keys) if drm_keys else 0}")
            
            if drm_keys:
                for key in drm_keys:
                    self.log(f"Ключ: {key[:32]}...")
            
            # Генерируем имя файла если не указано
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"kinescope_video_{timestamp}.mp4"
            
            self.log(f"Выходной файл: {output_filename}")
            
            # Подготавливаем аргументы для N_m3u8DL-RE
            args = [
                self.config.n_m3u8dl_re,
                mpd_url,
                "--save-name", output_filename,
                "--save-dir", self.config.output_dir,
                "--tmp-dir", self.config.temp_dir,
                "--check-segments-count", "false",
                "--binary-merge",  # Используем бинарное слияние
                "--log-level", "INFO",
                "--del-after-done",  # Удалять временные файлы после завершения
                "--no-date-info",  # Не добавлять дату в метаданные
                "--concurrent-download",  # Параллельное скачивание
            ]
            
            # Добавляем заголовки
            if referrer:
                args.extend(["--header", f"referer: {referrer}"])
                args.extend(["--header", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"])
                args.extend(["--header", "Origin: https://kinescope.io"])
            
            # Настройки качества
            if quality != "Авто":
                # Для конкретного качества используем select-video
                quality_map = {
                    "1080p": "1080",
                    "720p": "720", 
                    "480p": "480",
                    "360p": "360"
                }
                if quality in quality_map:
                    args.extend(["--select-video", f"quality={quality_map[quality]}"])
            else:
                # Для авто - автоматический выбор лучшего
                args.append("--auto-select")
            
            # Если есть ключи, добавляем их
            if drm_keys:
                for key in drm_keys:
                    args.extend(["--key", key])
                self.log(f"✅ Добавлено ключей для расшифровки: {len(drm_keys)}", "success")
            else:
                self.log("⚠️ ВНИМАНИЕ: Ключи DRM не переданы!", "warning")
                self.log("Видео будет скачано в зашифрованном виде!", "warning")
            
            # Добавляем путь к ffmpeg если есть
            if os.path.exists(self.config.ffmpeg):
                args.extend(["--ffmpeg-binary-path", self.config.ffmpeg])
            
            # Запускаем скачивание
            self.log("Запуск N_m3u8DL-RE...")
            self.log(f"Аргументы: {' '.join(args[:12])}...")
            
            success, output = self.run_command(args)
            
            if success:
                # Проверяем, создан ли файл
                output_path = os.path.join(self.config.output_dir, output_filename)
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    file_size_mb = file_size / (1024 * 1024)
                    self.log(f"✅ ВИДЕО УСПЕШНО СКАЧАНО!", "success")
                    self.log(f"📁 Файл: {output_filename}", "success")
                    self.log(f"📊 Размер: {file_size_mb:.2f} MB", "success")
                    self.log(f"📍 Путь: {output_path}", "success")
                    return True
                else:
                    self.log(f"❌ Файл не создан: {output_filename}", "error")
                    self.log("Проверьте папку downloads/", "info")
                    return False
            else:
                self.log("❌ Ошибка скачивания", "error")
                
                # Анализируем вывод
                if "key" in output.lower() or "decrypt" in output.lower():
                    self.log("🔑 Возможно, проблема с ключами DRM", "warning")
                elif "connection" in output.lower():
                    self.log("🌐 Проблема с подключением", "warning")
                elif "xml" in output.lower():
                    self.log("📄 Проблема с MPD файлом", "warning")
                
                return False
            
        except Exception as e:
            self.log(f"❌ Исключение при скачивании: {str(e)}", "error")
            return False
    
    def test_download(self) -> bool:
        """Тестовое скачивание (для отладки)"""
        self.log("🧪 ТЕСТИРОВАНИЕ N_m3u8DL-RE", "info")
        
        # Простая тестовая команда
        args = [self.config.n_m3u8dl_re, "--version"]
        success, output = self.run_command(args)
        
        if success:
            self.log(f"✅ N_m3u8DL-RE работает корректно", "success")
            self.log(f"Версия: {output[:50]}...", "info")
            return True
        else:
            self.log(f"❌ N_m3u8DL-RE не работает", "error")
            return False
    
    def cleanup_temp_files(self):
        """Очистка временных файлов"""
        if not self.config.keep_temp_files:
            try:
                if os.path.exists(self.config.temp_dir):
                    shutil.rmtree(self.config.temp_dir)
                    os.makedirs(self.config.temp_dir, exist_ok=True)
                    self.log("Временные файлы очищены")
            except Exception as e:
                self.log(f"Ошибка очистки временных файлов: {e}", "warning")