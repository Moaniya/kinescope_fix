"""
Конфигурация приложения
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AppConfig:
    """Конфигурация приложения"""
    # Пути к утилитам
    n_m3u8dl_re: str = "./utils/N_m3u8DL-RE/N_m3u8DL-RE.exe"
    ffmpeg: str = "./utils/N_m3u8DL-RE/ffmpeg.exe"
    mkvmerge: str = "./utils/mkvmerge/mkvmerge.exe"
    mp4decrypt: str = "./utils/mp4decrypt/mp4decrypt.exe"
    
    # Директории
    output_dir: str = "./downloads"
    temp_dir: str = "./temp"
    
    # Иконки
    app_icon: str = "./icons/app.ico"
    logo_image: str = "./icons/logo.png"
    
    # Настройки логотипа (уменьшили размеры)
    logo_width: int = 280
    logo_height: int = 70
    
    # Настройки загрузки
    keep_temp_files: bool = False
    max_retries: int = 3
    
    # DRM настройки
    browser_profile: str = "chrome"
    
    def __post_init__(self):
        """Создание директорий если их нет"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
    
    @classmethod
    def load_from_file(cls, config_path: str = "config.json") -> 'AppConfig':
        """Загрузка конфигурации из файла"""
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                return cls(**config_data)
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
        
        # Возвращаем конфигурацию по умолчанию
        return cls()
    
    def save_to_file(self, config_path: str = "config.json"):
        """Сохранение конфигурации в файл"""
        config_dict = {
            'n_m3u8dl_re': self.n_m3u8dl_re,
            'ffmpeg': self.ffmpeg,
            'mkvmerge': self.mkvmerge,
            'mp4decrypt': self.mp4decrypt,
            'output_dir': self.output_dir,
            'temp_dir': self.temp_dir,
            'app_icon': self.app_icon,
            'logo_image': self.logo_image,
            'logo_width': self.logo_width,
            'logo_height': self.logo_height,
            'keep_temp_files': self.keep_temp_files,
            'max_retries': self.max_retries,
            'browser_profile': self.browser_profile
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)


# Глобальный экземпляр конфигурации
config = AppConfig.load_from_file()