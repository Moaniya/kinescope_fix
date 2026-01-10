"""
Модуль для получения DRM ключей (адаптирован для ClearKey на Kinescope)
"""
import re
import json
import base64
import struct
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse


class KeyFetcher:
    """Получение ключей DRM для ClearKey (Kinescope)"""
    
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.session = requests.Session()
        
        # Заголовки как в браузере
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://kinescope.io',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        })
    
    def log(self, message: str, level: str = "info"):
        """Логирование сообщений"""
        if self.log_callback:
            self.log_callback(message, level)
        else:
            print(f"[{level.upper()}] {message}")
    
    def extract_kid_from_mpd(self, mpd_content: str) -> Optional[str]:
        """
        Извлечение KID (Key ID) из MPD файла.
        KID используется в ClearKey вместо PSSH.
        """
        try:
            # Парсим XML
            namespaces = {
                'cenc': 'urn:mpeg:cenc:2013',
                'mspr': 'urn:microsoft:playready'
            }
            
            # Регистрируем неймспейсы для упрощения поиска
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)
            
            root = ET.fromstring(mpd_content)
            
            # Ищем ContentProtection с ClearKey
            for cp in root.findall(".//{urn:mpeg:dash:schema:mpd:2011}ContentProtection"):
                scheme_id = cp.get('schemeIdUri', '')
                if scheme_id == 'urn:uuid:e2719d58-a985-b3c9-781a-b030af78d30e':  # ClearKey UUID
                    # Ищем default_KID
                    default_kid = cp.find('{urn:mpeg:cenc:2013}default_KID')
                    if default_kid is not None and default_kid.text:
                        kid_base64 = default_kid.text.strip()
                        self.log(f"Найден ClearKey KID: {kid_base64}")
                        return kid_base64
            
            # Альтернативный поиск: ищем любой default_KID
            for default_kid in root.findall(".//{urn:mpeg:cenc:2013}default_KID"):
                if default_kid.text:
                    kid_base64 = default_kid.text.strip()
                    self.log(f"Найден KID: {kid_base64}")
                    return kid_base64
            
            # Ищем в AdaptationSet или Representation
            for elem in root.iter():
                if 'default_KID' in elem.attrib:
                    kid_base64 = elem.attrib['default_KID']
                    self.log(f"Найден KID в атрибутах: {kid_base64}")
                    return kid_base64
            
            self.log("KID не найден в MPD. Будем использовать тестовый KID.", "warning")
            return None
            
        except Exception as e:
            self.log(f"Ошибка извлечения KID: {e}", "error")
            return None
    
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
                with open('debug_mpd.xml', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.log("MPD сохранен в debug_mpd.xml для отладки")
            except:
                pass
            
            return response.text
            
        except requests.exceptions.RequestException as e:
            self.log(f"Ошибка получения MPD: {e}", "error")
            return None
        except Exception as e:
            self.log(f"Неожиданная ошибка при получении MPD: {e}", "error")
            return None
    
    def find_license_url_from_json(self, json_file_path: str) -> Optional[str]:
        """Поиск URL лицензии в JSON файле (предпочтительный способ)"""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ищем в options -> playlist -> drm -> clearkey -> licenseUrl
            options = data.get('options', {})
            playlist = options.get('playlist', [])
            
            if playlist and isinstance(playlist, list) and len(playlist) > 0:
                first_item = playlist[0]
                drm_info = first_item.get('drm', {})
                clearkey_info = drm_info.get('clearkey', {})
                license_url = clearkey_info.get('licenseUrl', '')
                
                if license_url:
                    self.log(f"Найден license URL в JSON: {license_url}")
                    
                    # Проверяем, есть ли токен в URL
                    if 'token=' in license_url:
                        # Удаляем пустой токен, возможно сервер сам его добавит
                        license_url = license_url.split('token=')[0] + 'token='
                        self.log(f"URL лицензии очищен от пустого токена")
                    
                    return license_url
            
            # Ищем в rawOptions
            raw_options = data.get('rawOptions', {})
            if 'playlist' in raw_options:
                playlist = raw_options['playlist']
                if playlist and isinstance(playlist, list) and len(playlist) > 0:
                    first_item = playlist[0]
                    drm_info = first_item.get('drm', {})
                    clearkey_info = drm_info.get('clearkey', {})
                    license_url = clearkey_info.get('licenseUrl', '')
                    
                    if license_url:
                        self.log(f"Найден license URL в rawOptions: {license_url}")
                        return license_url
            
            self.log("License URL не найден в JSON", "warning")
            return None
            
        except Exception as e:
            self.log(f"Ошибка поиска license URL в JSON: {e}", "error")
            return None
    
    def create_clearkey_request(self, kid_base64: Optional[str] = None) -> Dict[str, Any]:
        """
        Создание ClearKey запроса в формате JSON.
        Формат соответствует спецификации EME ClearKey.
        """
        if kid_base64:
            # Декодируем base64 KID
            try:
                kid_bytes = base64.b64decode(kid_base64)
                
                # Преобразуем bytes в строку base64url (без padding)
                kid_base64url = base64.urlsafe_b64encode(kid_bytes).decode('utf-8').rstrip('=')
                
                request_data = {
                    "kids": [kid_base64url],
                    "type": "temporary"
                }
                
                self.log(f"Создан ClearKey запрос с KID: {kid_base64}")
                return request_data
                
            except Exception as e:
                self.log(f"Ошибка обработки KID: {e}", "error")
        
        # Если KID не найден, используем тестовый (как в Vineless)
        test_kid_base64 = "AAAAAAAAAAAAAAAAAAAAAA"
        test_kid_bytes = base64.b64decode(test_kid_base64 + "==")
        test_kid_base64url = base64.urlsafe_b64encode(test_kid_bytes).decode('utf-8').rstrip('=')
        
        request_data = {
            "kids": [test_kid_base64url],
            "type": "temporary"
        }
        
        self.log("Используется тестовый KID", "warning")
        return request_data
    
    def parse_clearkey_response(self, response_text: str) -> List[str]:
        """
        Парсинг ответа от сервера ClearKey.
        Ожидаемый формат: {"keys": [{"kty":"oct","k":"BASE64_KEY","kid":"BASE64_KID"}]}
        """
        keys = []
        
        try:
            response_data = json.loads(response_text)
            
            if 'keys' in response_data and isinstance(response_data['keys'], list):
                for key_info in response_data['keys']:
                    if 'k' in key_info and 'kid' in key_info:
                        # Ключ в формате base64 -> hex для N_m3u8DL-RE
                        key_b64 = key_info['k']
                        kid_b64 = key_info['kid']
                        
                        # Добавляем padding если нужно
                        padding = 4 - len(key_b64) % 4
                        if padding != 4:
                            key_b64 += '=' * padding
                        
                        try:
                            key_bytes = base64.b64decode(key_b64)
                            key_hex = key_bytes.hex()
                            
                            # KID тоже конвертируем
                            kid_padding = 4 - len(kid_b64) % 4
                            if kid_padding != 4:
                                kid_b64 += '=' * kid_padding
                            
                            kid_bytes = base64.b64decode(kid_b64)
                            kid_hex = kid_bytes.hex()
                            
                            key_str = f"{kid_hex}:{key_hex}"
                            keys.append(key_str)
                            
                            self.log(f"Получен ключ: {key_str[:32]}...")
                            
                        except Exception as e:
                            self.log(f"Ошибка декодирования ключа: {e}", "warning")
            
            if not keys:
                # Пробуем альтернативный формат
                self.log("Пробуем альтернативные форматы ответа...")
                
                # Просто ищем base64 строки
                import re
                base64_pattern = r'[A-Za-z0-9+/=]{20,}'
                matches = re.findall(base64_pattern, response_text)
                
                for match in matches:
                    if len(match) >= 24:  # Минимальная длина для ключа
                        try:
                            # Пробуем декодировать
                            decoded = base64.b64decode(match + '==')
                            if len(decoded) == 16:  # 16 байт = 128 бит (типичный размер ключа)
                                key_hex = decoded.hex()
                                # Используем тестовый KID
                                test_kid_hex = "00000000000000000000000000000000"
                                keys.append(f"{test_kid_hex}:{key_hex}")
                                self.log(f"Найден возможный ключ в ответе")
                                break
                        except:
                            pass
        
        except json.JSONDecodeError:
            self.log("Ответ не в JSON формате. Пробуем извлечь ключи из бинарного ответа...", "warning")
            
            # Пробуем извлечь ключи из бинарного ответа
            if len(response_text) >= 16:
                # Предполагаем, что ключ - это первые 16 байт
                key_bytes = response_text[:16].encode('latin-1') if isinstance(response_text, str) else response_text[:16]
                key_hex = key_bytes.hex()
                test_kid_hex = "00000000000000000000000000000000"
                keys.append(f"{test_kid_hex}:{key_hex}")
                self.log(f"Извлечен ключ из бинарного ответа")
        
        except Exception as e:
            self.log(f"Ошибка парсинга ответа: {e}", "error")
        
        return keys
    
    def send_license_request(self, license_url: str, request_data: Dict[str, Any], referrer: str) -> Optional[str]:
        """Отправка запроса на сервер лицензий"""
        try:
            headers = {
                'Referer': referrer,
                'Content-Type': 'application/json',
                'Origin': 'https://kinescope.io'
            }
            
            self.log(f"Отправка запроса на: {license_url}")
            self.log(f"Данные запроса: {json.dumps(request_data, indent=2)}")
            
            response = self.session.post(
                license_url,
                json=request_data,
                headers=headers,
                timeout=30
            )
            
            self.log(f"Статус ответа: {response.status_code}")
            self.log(f"Заголовки ответа: {dict(response.headers)}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                if 'json' in content_type:
                    response_text = response.text
                    self.log(f"Ответ JSON, длина: {len(response_text)} символов")
                else:
                    # Пробуем разные кодировки
                    response_text = response.text
                    self.log(f"Ответ не-JSON, длина: {len(response_text)} символов")
                
                # Сохраняем ответ для отладки
                try:
                    with open('debug_license_response.txt', 'w', encoding='utf-8') as f:
                        f.write(f"URL: {license_url}\n")
                        f.write(f"Status: {response.status_code}\n")
                        f.write(f"Headers: {dict(response.headers)}\n")
                        f.write(f"Body:\n{response_text}\n")
                    self.log("Ответ сохранен в debug_license_response.txt")
                except:
                    pass
                
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
    
    def get_keys(self, mpd_url: str, referrer: str, json_file_path: Optional[str] = None) -> List[str]:
        """
        Получение DRM ключей для ClearKey
        
        Args:
            mpd_url: URL MPD файла
            referrer: Referrer для запросов
            json_file_path: Путь к JSON файлу (для получения license URL)
            
        Returns:
            Список ключей в формате KID:KEY
        """
        self.log("Начало получения ключей для ClearKey...")
        
        keys = []
        
        try:
            # 1. Получаем MPD для извлечения KID
            self.log("Получение MPD...")
            mpd_content = self.get_mpd_content(mpd_url, referrer)
            if not mpd_content:
                self.log("Не удалось получить MPD", "error")
                return keys
            
            # 2. Извлекаем KID из MPD
            self.log("Извлечение KID из MPD...")
            kid_base64 = self.extract_kid_from_mpd(mpd_content)
            
            # 3. Получаем license URL (предпочтительно из JSON)
            license_url = None
            if json_file_path:
                license_url = self.find_license_url_from_json(json_file_path)
            
            if not license_url:
                # Если нет в JSON, пробуем стандартный URL Kinescope
                video_id = mpd_url.split('/')[-2] if len(mpd_url.split('/')) >= 2 else 'unknown'
                license_url = f"https://license.kinescope.io/v1/vod/{video_id}/acquire/clearkey"
                self.log(f"Используем стандартный license URL: {license_url}")
            
            # 4. Создаем ClearKey запрос
            self.log("Создание ClearKey запроса...")
            request_data = self.create_clearkey_request(kid_base64)
            
            # 5. Отправляем запрос на сервер лицензий
            self.log("Отправка запроса на сервер лицензий...")
            response_text = self.send_license_request(license_url, request_data, referrer)
            
            if not response_text:
                self.log("Не удалось получить ответ от сервера лицензий", "error")
                return keys
            
            # 6. Парсим ответ и извлекаем ключи
            self.log("Парсинг ответа сервера...")
            keys = self.parse_clearkey_response(response_text)
            
            if keys:
                self.log(f"Успешно получено {len(keys)} ключей!", "success")
            else:
                self.log("Не удалось извлечь ключи из ответа", "warning")
                # Пробуем альтернативный метод
                keys = self.try_alternative_methods(response_text)
            
        except Exception as e:
            self.log(f"Критическая ошибка получения ключей: {e}", "error")
        
        return keys
    
    def try_alternative_methods(self, response_text: str) -> List[str]:
        """Альтернативные методы извлечения ключей"""
        keys = []
        
        try:
            # Метод 1: Ищем base64 строки определенной длины
            import re
            
            # Шаблон для base64 (длиной 22-24 символа без padding)
            b64_pattern = r'[A-Za-z0-9+/]{22,24}'
            matches = re.findall(b64_pattern, response_text)
            
            for match in matches:
                # Пробуем декодировать как ключ (16 байт = 128 бит)
                try:
                    decoded = base64.b64decode(match + '==')
                    if len(decoded) == 16:
                        key_hex = decoded.hex()
                        test_kid_hex = "00000000000000000000000000000000"
                        key_str = f"{test_kid_hex}:{key_hex}"
                        keys.append(key_str)
                        self.log(f"Альтернативный метод: найден ключ {key_hex[:8]}...")
                except:
                    continue
            
            # Метод 2: Ищем hex строки (32 символа = 16 байт)
            hex_pattern = r'[0-9a-fA-F]{32}'
            hex_matches = re.findall(hex_pattern, response_text)
            
            for hex_match in hex_matches:
                if len(hex_match) == 32:
                    test_kid_hex = "00000000000000000000000000000000"
                    key_str = f"{test_kid_hex}:{hex_match}"
                    if key_str not in keys:
                        keys.append(key_str)
                        self.log(f"Альтернативный метод: найден hex ключ {hex_match[:8]}...")
        
        except Exception as e:
            self.log(f"Ошибка в альтернативных методах: {e}", "warning")
        
        return keys