"""
Модуль для получения DRM ключей (адаптирован под реальный формат Kinescope)
"""
import re
import json
import base64
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urljoin, urlparse


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
    
    def find_kid_in_mpd(self, mpd_content: str) -> Optional[str]:
        """
        Поиск KID в MPD файле.
        В Kinescope KID может быть в разных местах.
        """
        try:
            # Парсим XML
            root = ET.fromstring(mpd_content)
            
            # Регистрируем неймспейсы
            namespaces = {
                'cenc': 'urn:mpeg:cenc:2013',
                'mspr': 'urn:microsoft:playready',
                'mpd': 'urn:mpeg:dash:schema:mpd:2011'
            }
            
            # Ищем во всех возможных местах
            search_paths = [
                ".//{urn:mpeg:dash:schema:mpd:2011}ContentProtection[@schemeIdUri='urn:uuid:e2719d58-a985-b3c9-781a-b030af78d30e']/{urn:mpeg:cenc:2013}default_KID",
                ".//{urn:mpeg:cenc:2013}default_KID",
                ".//*[@default_KID]",
                ".//ContentProtection/default_KID",
                ".//default_KID"
            ]
            
            for path in search_paths:
                try:
                    elements = root.findall(path)
                    for elem in elements:
                        if elem.text:
                            kid = elem.text.strip()
                            if kid and len(kid) > 10:
                                self.log(f"Найден KID по пути {path}: {kid}")
                                return kid
                except:
                    continue
            
            # Альтернативный поиск по атрибутам
            for elem in root.iter():
                if 'default_KID' in elem.attrib:
                    kid = elem.attrib['default_KID']
                    if kid and len(kid) > 10:
                        self.log(f"Найден KID в атрибутах: {kid}")
                        return kid
            
            self.log("KID не найден стандартными методами. Используем альтернативный поиск.", "warning")
            
            # Пробуем найти в тексте MPD
            kid_patterns = [
                r'default_KID[="\s]*([A-Za-z0-9+/=]{20,})',
                r'cenc:default_KID[="\s]*([A-Za-z0-9+/=]{20,})',
                r'kid[="\s]*([A-Za-z0-9+/=]{20,})',
            ]
            
            for pattern in kid_patterns:
                matches = re.findall(pattern, mpd_content)
                for match in matches:
                    if len(match) >= 20:
                        self.log(f"Найден KID по шаблону: {match}")
                        return match
            
            return None
            
        except Exception as e:
            self.log(f"Ошибка поиска KID в MPD: {e}", "error")
            return None
    
    def extract_kid_from_init_segment(self, mpd_url: str, referrer: str) -> Optional[str]:
        """
        Извлечение KID из initialization segment.
        Иногда KID находится не в MPD, а в медиа-сегментах.
        """
        try:
            # Сначала получаем MPD для поиска initialization URL
            mpd_response = self.session.get(mpd_url, headers={'Referer': referrer}, timeout=30)
            mpd_response.raise_for_status()
            mpd_content = mpd_response.text
            
            # Ищем initialization URL в MPD
            init_patterns = [
                r'initialization="([^"]+)"',
                r'<BaseURL>([^<]+\.mpd[^<]*)</BaseURL>',
                r'media="([^"]+)"',
            ]
            
            init_url = None
            base_url = '/'.join(mpd_url.split('/')[:-1]) + '/'  # Базовый URL
            
            for pattern in init_patterns:
                matches = re.findall(pattern, mpd_content)
                for match in matches:
                    if '.mpd' in match or 'init' in match.lower():
                        if match.startswith('http'):
                            init_url = match
                        else:
                            init_url = urljoin(base_url, match)
                        break
                if init_url:
                    break
            
            if not init_url:
                # Пробуем стандартный путь
                video_id = mpd_url.split('/')[-2] if len(mpd_url.split('/')) >= 2 else 'unknown'
                init_url = f"https://kinescope.io/{video_id}/init.mp4"
            
            self.log(f"Пробуем получить KID из init segment: {init_url}")
            
            # Скачиваем первые 1024 байта init segment
            headers = {'Referer': referrer, 'Range': 'bytes=0-1023'}
            response = self.session.get(init_url, headers=headers, timeout=30)
            
            if response.status_code in [200, 206]:
                # Ищем 'tenc' или 'schi' атомы в MP4 (там может быть KID)
                content = response.content
                
                # Простой поиск base64 строк в бинарных данных
                import re
                text_content = content.decode('latin-1', errors='ignore')
                b64_matches = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', text_content)
                
                for match in b64_matches:
                    if len(match) >= 20:
                        try:
                            # Пробуем декодировать
                            decoded = base64.b64decode(match + '==')
                            if len(decoded) == 16:  # 16 байт = KID
                                kid_base64 = base64.b64encode(decoded).decode('utf-8').rstrip('=')
                                self.log(f"Найден KID в init segment: {kid_base64}")
                                return kid_base64
                        except:
                            continue
            
            return None
            
        except Exception as e:
            self.log(f"Ошибка извлечения KID из init segment: {e}", "warning")
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
            
            # 3. В driver -> drmInfo (если есть)
            if not license_url and 'state' in data:
                driver = data['state'].get('driver', {})
                drm_info = driver.get('drmInfo', {})
                if drm_info.get('keySystem') == 'org.w3.clearkey':
                    # Стандартный URL для Kinescope
                    video_id = data['state'].get('videoId', '')
                    if video_id:
                        license_url = f"https://license.kinescope.io/v1/vod/{video_id}/acquire/clearkey?token="
            
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
    
    def create_kinescope_request(self, kid_base64: Optional[str]) -> Dict[str, Any]:
        """
        Создание запроса в формате Kinescope.
        На основе реального перехвата: {"kids": ["ckJuYnhTSjlpZW9VMUFVPQ"], "type": "temporary"}
        """
        if kid_base64:
            # Убедимся, что KID в правильном формате (без padding)
            kid_clean = kid_base64.rstrip('=')
            
            request_data = {
                "kids": [kid_clean],
                "type": "temporary"
            }
            
            self.log(f"Создан запрос с KID: {kid_clean}")
            return request_data
        else:
            # Если KID не найден, используем тестовый из перехвата
            test_kid = "ckJuYnhTSjlpZW9VMUFVPQ"  # Из реального запроса
            request_data = {
                "kids": [test_kid],
                "type": "temporary"
            }
            
            self.log(f"Используем тестовый KID из перехвата: {test_kid}", "warning")
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
            # 1. Получаем MPD
            self.log("Получение MPD...")
            headers = {'Referer': referrer}
            mpd_response = self.session.get(mpd_url, headers=headers, timeout=30)
            mpd_response.raise_for_status()
            mpd_content = mpd_response.text
            
            self.log(f"MPD получен, размер: {len(mpd_content)} байт")
            
            # Сохраняем MPD для отладки
            try:
                with open('debug_mpd_kinescope.xml', 'w', encoding='utf-8') as f:
                    f.write(mpd_content)
                self.log("MPD сохранен в debug_mpd_kinescope.xml")
            except:
                pass
            
            # 2. Ищем KID в MPD
            self.log("Поиск KID в MPD...")
            kid_base64 = self.find_kid_in_mpd(mpd_content)
            
            if not kid_base64:
                self.log("KID не найден в MPD. Пробуем извлечь из init segment...", "warning")
                kid_base64 = self.extract_kid_from_init_segment(mpd_url, referrer)
            
            # 3. Получаем license URL
            license_url = None
            if json_file_path:
                license_url = self.get_license_url_from_json(json_file_path)
            
            if not license_url:
                # Пробуем стандартный URL
                video_id = mpd_url.split('/')[-2] if len(mpd_url.split('/')) >= 2 else 'unknown'
                license_url = f"https://license.kinescope.io/v1/vod/{video_id}/acquire/clearkey"
                self.log(f"Используем стандартный license URL: {license_url}")
            
            # 4. Создаем запрос в формате Kinescope
            self.log("Создание запроса...")
            request_data = self.create_kinescope_request(kid_base64)
            
            # 5. Отправляем запрос
            self.log("Отправка запроса на сервер лицензий...")
            response_text = self.send_license_request(license_url, request_data, referrer)
            
            if not response_text:
                self.log("Не удалось получить ответ от сервера", "error")
                return keys
            
            # 6. Парсим ответ и извлекаем ключи
            self.log("Парсинг ответа...")
            keys = self.parse_kinescope_response(response_text)
            
            if keys:
                self.log(f"Успешно получено {len(keys)} ключей!", "success")
                for key in keys:
                    self.log(f"Ключ: {key}")
            else:
                self.log("Не удалось получить ключи", "error")
                # Пробуем использовать тестовый запрос с KID из перехвата
                self.log("Пробуем с тестовым KID из реального запроса...")
                test_request = {"kids": ["ckJuYnhTSjlpZW9VMUFVPQ"], "type": "temporary"}
                test_response = self.send_license_request(license_url, test_request, referrer)
                if test_response:
                    keys = self.parse_kinescope_response(test_response)
            
        except Exception as e:
            self.log(f"Критическая ошибка получения ключей: {e}", "error")
        
        return keys