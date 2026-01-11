"""
Модуль для получения DRM ключей (адаптирован под реальный формат Kinescope)
"""
import re
import json
import base64
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin


class KeyFetcher:
    """Получение DRM ключей для Kinescope (ClearKey)"""
    
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.session = requests.Session()
        
        # Заголовки как в реальном браузере Firefox
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://kinescope.io',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })
    
    def log(self, message: str, level: str = "info"):
        """Логирование сообщений"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level.upper()}] {message}")
    
    def get_mpd_content(self, mpd_url: str, referrer: str) -> Optional[str]:
        """Получение содержимого MPD файла"""
        try:
            headers = {'Referer': referrer}
            response = self.session.get(mpd_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            content_length = len(response.content)
            self.log(f"MPD получен, размер: {content_length} байт")
            
            # Сохраняем MPD для отладки
            try:
                with open('debug_mpd_kinescope.xml', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.log("MPD сохранен в debug_mpd_kinescope.xml")
            except:
                pass
            
            return response.text
            
        except Exception as e:
            self.log(f"Ошибка получения MPD: {e}", "error")
            return None
    
    def get_license_url_from_json(self, json_file_path: str) -> Optional[str]:
        """Получение URL лицензии из JSON файла"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ищем во всех возможных местах
            license_url = None
            
            # 1. В options -> playlist -> drm -> clearkey -> licenseUrl
            options = data.get('options', {})
            playlist = options.get('playlist', [])
            if playlist and len(playlist) > 0:
                drm_info = playlist[0].get('drm', {})
                clearkey_info = drm_info.get('clearkey', {})
                license_url = clearkey_info.get('licenseUrl', '')
            
            # 2. В rawOptions
            if not license_url:
                raw_options = data.get('rawOptions', {})
                if 'playlist' in raw_options and raw_options['playlist']:
                    drm_info = raw_options['playlist'][0].get('drm', {})
                    clearkey_info = drm_info.get('clearkey', {})
                    license_url = clearkey_info.get('licenseUrl', '')
            
            if license_url:
                # Очищаем от пустого токена
                if 'token=' in license_url and license_url.endswith('token='):
                    license_url = license_url[:-6]  # Убираем 'token='
                self.log(f"Найден license URL: {license_url}")
                return license_url
            
            self.log("License URL не найден в JSON", "warning")
            return None
            
        except Exception as e:
            self.log(f"Ошибка получения license URL из JSON: {e}", "error")
            return None
    
    def create_kinescope_request(self) -> Dict[str, Any]:
        """
        Создание запроса в формате Kinescope.
        Используем тестовый KID из реального перехвата.
        """
        # Тестовый KID из реального запроса браузера
        test_kid = "ckJuYnhTSjlpZW9VMUFVPQ"
        request_data = {
            "kids": [test_kid],
            "type": "temporary"
        }
        
        self.log(f"Используем тестовый KID из перехвата: {test_kid}")
        return request_data
    
    def send_license_request(self, license_url: str, request_data: Dict[str, Any], referrer: str) -> Optional[str]:
        """Отправка запроса на сервер лицензий Kinescope"""
        try:
            headers = {
                'Referer': referrer,
                'Origin': 'https://kinescope.io',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
            }
            
            self.log(f"Отправка POST запроса на: {license_url}")
            self.log(f"Данные запроса: {json.dumps(request_data, indent=2)}")
            
            response = self.session.post(
                license_url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            self.log(f"Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                response_text = response.text
                self.log(f"Ответ получен, длина: {len(response_text)} символов")
                
                # Сохраняем для отладки
                try:
                    with open('debug_license_response_kinescope.txt', 'w', encoding='utf-8') as f:
                        f.write(f"URL: {license_url}\n")
                        f.write(f"Request: {json.dumps(request_data, indent=2)}\n")
                        f.write(f"Status: {response.status_code}\n")
                        f.write(f"Response:\n{response_text}\n")
                    self.log("Ответ сохранен в debug_license_response_kinescope.txt")
                except Exception as e:
                    self.log(f"Не удалось сохранить ответ: {e}", "warning")
                
                return response_text
            else:
                self.log(f"Ошибка сервера: {response.status_code}", "error")
                self.log(f"Текст ошибки: {response.text[:500]}", "error")
                return None
                
        except requests.exceptions.RequestException as e:
            self.log(f"Ошибка отправки запроса: {e}", "error")
            return None
        except Exception as e:
            self.log(f"Неожиданная ошибка: {e}", "error")
            return None
    
    def parse_kinescope_response(self, response_text: str) -> List[str]:
        """
        Парсинг ответа от сервера Kinescope.
        Формат: {"keys": [{"kty":"oct","k":"bndCTzZMRnpzSmVocEs0PQ","kid":"ckJuYnhTSjlpZW9VMUFVPQ"}]}
        """
        keys = []
        
        try:
            response_data = json.loads(response_text)
            
            if 'keys' in response_data and isinstance(response_data['keys'], list):
                for key_info in response_data['keys']:
                    if 'k' in key_info and 'kid' in key_info:
                        key_b64 = key_info['k']  # Без padding
                        kid_b64 = key_info['kid']  # Без padding
                        
                        self.log(f"Найден ключ: kid={kid_b64}, key={key_b64}")
                        
                        try:
                            # Добавляем padding если нужно и декодируем
                            kid_padded = kid_b64 + '=' * (4 - len(kid_b64) % 4)
                            key_padded = key_b64 + '=' * (4 - len(key_b64) % 4)
                            
                            kid_bytes = base64.b64decode(kid_padded)
                            key_bytes = base64.b64decode(key_padded)
                            
                            # Преобразуем в HEX для N_m3u8DL-RE
                            kid_hex = kid_bytes.hex()
                            key_hex = key_bytes.hex()
                            
                            key_str = f"{kid_hex}:{key_hex}"
                            keys.append(key_str)
                            
                            self.log(f"Преобразовано в HEX: {key_str}")
                            
                        except Exception as e:
                            self.log(f"Ошибка декодирования ключа: {e}", "warning")
            
            if not keys:
                self.log("Ключи не найдены в ответе", "warning")
                self.log(f"Полный ответ: {response_text}")
        
        except json.JSONDecodeError:
            self.log("Ответ не в JSON формате", "error")
            self.log(f"Ответ: {response_text[:500]}")
        except Exception as e:
            self.log(f"Ошибка парсинга ответа: {e}", "error")
        
        return keys
    
    def get_keys(self, mpd_url: str, referrer: str, json_file_path: Optional[str] = None) -> List[str]:
        """
        Получение DRM ключей для Kinescope
        
        Args:
            mpd_url: URL MPD файла
            referrer: Referrer для запросов
            json_file_path: Путь к JSON файлу
            
        Returns:
            Список ключей в формате KID:KEY (HEX)
        """
        self.log("Начало получения ключей для Kinescope...")
        
        keys = []
        
        try:
            # 1. Получаем MPD (только для логов)
            self.log("Получение MPD...")
            mpd_content = self.get_mpd_content(mpd_url, referrer)
            
            if not mpd_content:
                self.log("Не удалось получить MPD, но продолжаем...", "warning")
            
            # 2. Получаем license URL
            license_url = None
            if json_file_path:
                license_url = self.get_license_url_from_json(json_file_path)
            
            if not license_url:
                # Пробуем стандартный URL
                video_id = mpd_url.split('/')[-2] if len(mpd_url.split('/')) >= 2 else 'unknown'
                license_url = f"https://license.kinescope.io/v1/vod/{video_id}/acquire/clearkey"
                self.log(f"Используем стандартный license URL: {license_url}")
            
            # 3. Создаем запрос в формате Kinescope
            self.log("Создание запроса...")
            request_data = self.create_kinescope_request()
            
            # 4. Отправляем запрос
            self.log("Отправка запроса на сервер лицензий...")
            response_text = self.send_license_request(license_url, request_data, referrer)
            
            if not response_text:
                self.log("Не удалось получить ответ от сервера", "error")
                return keys
            
            # 5. Парсим ответ и извлекаем ключи
            self.log("Парсинг ответа...")
            keys = self.parse_kinescope_response(response_text)
            
            if keys:
                self.log(f"✅ Успешно получено {len(keys)} ключей!", "success")
                for key in keys:
                    self.log(f"🔑 Ключ: {key}")
            else:
                self.log("❌ Не удалось получить ключи", "error")
            
        except Exception as e:
            self.log(f"Критическая ошибка получения ключей: {e}", "error")
        
        return keys