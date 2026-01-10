"""
Парсер JSON файлов Kinescope
"""
import json
import re
from typing import Dict, Any, Optional, List


class JSONParser:
    """Парсит JSON файлы и извлекает данные"""
    
    @staticmethod
    def parse_json_file(file_path: str) -> Dict[str, Any]:
        """
        Парсит JSON файл и возвращает словарь с данными
        
        Args:
            file_path: Путь к JSON файлу
            
        Returns:
            Словарь с данными
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {
                'success': False,
                'url': '',
                'referrer': '',
                'm3u8_url': '',
                'mpd_url': '',
                'playlist': [],
                'video_id': '',
                'video_title': '',
                'qualities': [],
                'error': ''
            }
            
            # Извлекаем основные данные
            result['url'] = data.get('url', '')
            result['referrer'] = data.get('referrer', '')
            
            # Извлекаем playlist - ищем в разных местах
            playlist = None
            
            # Сначала ищем в options -> playlist
            options = data.get('options', {})
            if 'playlist' in options:
                playlist = options.get('playlist', [])
            # Затем в rawOptions -> playlist
            elif 'rawOptions' in data:
                raw_options = data.get('rawOptions', {})
                if 'playlist' in raw_options:
                    playlist = raw_options.get('playlist', [])
            
            if playlist and isinstance(playlist, list) and len(playlist) > 0:
                result['playlist'] = playlist
                first_item = playlist[0]
                
                # Видео ID и название
                result['video_id'] = first_item.get('id', '')
                result['video_title'] = first_item.get('title', '')
                
                # Получаем sources
                sources = first_item.get('sources', {})
                
                # Пробуем получить shakahls URL (m3u8)
                if 'shakahls' in sources:
                    shakahls = sources['shakahls']
                    m3u8_url = shakahls.get('src', '')
                    
                    if m3u8_url:
                        result['m3u8_url'] = m3u8_url
                        # Конвертируем в MPD URL
                        result['mpd_url'] = m3u8_url.replace('.m3u8', '.mpd')
                        # Удаляем параметры после .m3u8
                        if '?' in result['mpd_url']:
                            base_url = result['mpd_url'].split('?')[0]
                            result['mpd_url'] = base_url
                
                # Также пробуем получить из hls
                elif 'hls' in sources:
                    hls = sources['hls']
                    m3u8_url = hls.get('src', '')
                    
                    if m3u8_url:
                        result['m3u8_url'] = m3u8_url
                        result['mpd_url'] = m3u8_url.replace('.m3u8', '.mpd')
                        # Удаляем параметры после .m3u8
                        if '?' in result['mpd_url']:
                            base_url = result['mpd_url'].split('?')[0]
                            result['mpd_url'] = base_url
                
                # Извлекаем доступные качества
                if 'qualityLabels' in first_item:
                    quality_labels = first_item.get('qualityLabels', {})
                    if 'list' in quality_labels:
                        qualities = quality_labels['list']
                        result['qualities'] = [f"{q}p" for q in qualities if isinstance(q, (int, float))]
                    else:
                        # Ищем в ключах qualityLabels
                        qualities = []
                        for key in quality_labels.keys():
                            if key.isdigit():
                                qualities.append(f"{key}p")
                        result['qualities'] = sorted(qualities, key=lambda x: int(x[:-1]), reverse=True)
            
            result['success'] = True
            return result
            
        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f'Ошибка парсинга JSON: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Ошибка обработки файла: {str(e)}'
            }