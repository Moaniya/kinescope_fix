"""
Главное окно приложения Kinescope Downloader
"""
import os
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton,
    QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QGridLayout, QComboBox, QCheckBox, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QFont

# Импортируем конфигурацию
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import config

# Импорты модулей
try:
    from parsers.json_parser import JSONParser
    JSON_PARSER_AVAILABLE = True
except ImportError:
    JSONParser = None
    JSON_PARSER_AVAILABLE = False
    print("Предупреждение: Модуль JSONParser не найден")

try:
    from drm.key_fetcher import KeyFetcher
    KEY_FETCHER_AVAILABLE = True
except ImportError:
    KeyFetcher = None
    KEY_FETCHER_AVAILABLE = False
    print("Предупреждение: Модуль KeyFetcher не найден")

try:
    from core.downloader import VideoDownloader
    DOWNLOADER_AVAILABLE = True
except ImportError:
    VideoDownloader = None
    DOWNLOADER_AVAILABLE = False
    print("Предупреждение: Модуль VideoDownloader не найден")


class DownloadThread(QThread):
    """Поток для скачивания видео"""
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool)
    
    def __init__(self, downloader, mpd_url, referrer, quality, audio_lang, drm_keys=None):
        super().__init__()
        self.downloader = downloader
        self.mpd_url = mpd_url
        self.referrer = referrer
        self.quality = quality
        self.audio_lang = audio_lang
        self.drm_keys = drm_keys
    
    def run(self):
        try:
            if self.drm_keys:
                self.downloader.drm_keys = self.drm_keys
            
            success = self.downloader.download_video(
                mpd_url=self.mpd_url,
                referrer=self.referrer,
                quality=self.quality,
                audio_lang=self.audio_lang,
                drm_keys=self.drm_keys
            )
            
            self.finished_signal.emit(success)
            
        except Exception as e:
            self.log_signal.emit(f"Ошибка в потоке скачивания: {str(e)}", "error")
            self.finished_signal.emit(False)


class MainWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self):
        super().__init__()
        self.config = config
        self.json_file_path = None
        self.log_text = None
        self.drm_keys = None
        self.download_thread = None
        
        self.init_ui()
        self.apply_styles()
        
        # Теперь можно логировать
        self.log("Приложение запущено")
        self.check_modules_availability()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        self.setWindowTitle("Kinescope Downloader")
        self.setWindowIcon(QIcon(self.config.app_icon))
        self.setMinimumSize(900, 750)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(15, 10, 15, 10)
        
        # === ЛОГОТИП ===
        logo_label = QLabel()
        if os.path.exists(self.config.logo_image):
            pixmap = QPixmap(self.config.logo_image)
            
            # Масштабируем до фиксированного размера с сохранением пропорций
            scaled_pixmap = pixmap.scaled(
                self.config.logo_width,
                self.config.logo_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            logo_label.setPixmap(scaled_pixmap)
            self.logo_info = f"Логотип: {pixmap.width()}x{pixmap.height()} -> {scaled_pixmap.width()}x{scaled_pixmap.height()}"
        else:
            logo_label.setText("KINESCOPE DOWNLOADER")
            logo_label.setFont(QFont("Arial", 18, QFont.Bold))
            logo_label.setStyleSheet("color: #0078d7;")
            self.logo_info = "Логотип не найден, используется текст"
        
        logo_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(logo_label)
        
        # Добавим небольшой отступ после логотипа
        main_layout.addSpacing(10)
        
        # === ГРУППА: ЗАГРУЗКА JSON ===
        json_group = QGroupBox("Загрузка JSON файла")
        json_layout = QGridLayout()
        json_layout.setSpacing(6)
        
        # Поле для пути к файлу
        self.json_path_edit = QLineEdit()
        self.json_path_edit.setPlaceholderText("Выберите JSON файл...")
        json_layout.addWidget(QLabel("Файл JSON:"), 0, 0)
        json_layout.addWidget(self.json_path_edit, 0, 1)
        
        # Кнопка выбора файла
        browse_btn = QPushButton("Обзор...")
        browse_btn.clicked.connect(self.browse_json_file)
        json_layout.addWidget(browse_btn, 0, 2)
        
        # Кнопка парсинга
        self.parse_btn = QPushButton("Парсить JSON")
        self.parse_btn.clicked.connect(self.parse_json)
        self.parse_btn.setEnabled(False)
        json_layout.addWidget(self.parse_btn, 1, 0, 1, 3)
        
        json_group.setLayout(json_layout)
        main_layout.addWidget(json_group)
        
        # === ГРУППА: ИНФОРМАЦИЯ О ВИДЕО ===
        info_group = QGroupBox("Информация о видео")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # URL
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setFixedWidth(80)
        url_layout.addWidget(url_label)
        self.url_edit = QLineEdit()
        self.url_edit.setReadOnly(True)
        url_layout.addWidget(self.url_edit)
        info_layout.addLayout(url_layout)
        
        # Referrer
        ref_layout = QHBoxLayout()
        ref_label = QLabel("Referrer:")
        ref_label.setFixedWidth(80)
        ref_layout.addWidget(ref_label)
        self.ref_edit = QLineEdit()
        self.ref_edit.setReadOnly(True)
        ref_layout.addWidget(self.ref_edit)
        info_layout.addLayout(ref_layout)
        
        # MPD URL
        mpd_layout = QHBoxLayout()
        mpd_label = QLabel("MPD URL:")
        mpd_label.setFixedWidth(80)
        mpd_layout.addWidget(mpd_label)
        self.mpd_edit = QLineEdit()
        self.mpd_edit.setReadOnly(True)
        mpd_layout.addWidget(self.mpd_edit)
        info_layout.addLayout(mpd_layout)
        
        # M3U8 URL
        m3u8_layout = QHBoxLayout()
        m3u8_label = QLabel("M3U8 URL:")
        m3u8_label.setFixedWidth(80)
        m3u8_layout.addWidget(m3u8_label)
        self.m3u8_edit = QLineEdit()
        self.m3u8_edit.setReadOnly(True)
        m3u8_layout.addWidget(self.m3u8_edit)
        info_layout.addLayout(m3u8_layout)
        
        # Видео ID и название
        id_layout = QHBoxLayout()
        id_label = QLabel("Video ID:")
        id_label.setFixedWidth(80)
        id_layout.addWidget(id_label)
        self.video_id_edit = QLineEdit()
        self.video_id_edit.setReadOnly(True)
        id_layout.addWidget(self.video_id_edit)
        
        title_label = QLabel("Название:")
        title_label.setFixedWidth(70)
        id_layout.addWidget(title_label)
        self.video_title_edit = QLineEdit()
        self.video_title_edit.setReadOnly(True)
        id_layout.addWidget(self.video_title_edit)
        
        info_layout.addLayout(id_layout)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # === ГРУППА: НАСТРОЙКИ СКАЧИВАНИЯ ===
        settings_group = QGroupBox("Настройки скачивания")
        settings_layout = QGridLayout()
        settings_layout.setSpacing(6)
        
        # Качество
        settings_layout.addWidget(QLabel("Качество:"), 0, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Авто", "1080p", "720p", "480p", "360p"])
        settings_layout.addWidget(self.quality_combo, 0, 1)
        
        # Аудио дорожка
        settings_layout.addWidget(QLabel("Аудио:"), 1, 0)
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(["Авто", "Русский", "Английский"])
        settings_layout.addWidget(self.audio_combo, 1, 1)
        
        # Сохранять временные файлы
        self.keep_temp_check = QCheckBox("Сохранять временные файлы")
        settings_layout.addWidget(self.keep_temp_check, 2, 0, 1, 2)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # === ГРУППА: ПРОГРЕСС И ЛОГ ===
        progress_group = QGroupBox("Прогресс")
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)
        
        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        # Лог
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        progress_layout.addWidget(self.log_text)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # === КНОПКИ УПРАВЛЕНИЯ ===
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Кнопка получения ключей
        self.keys_btn = QPushButton("Получить ключи")
        self.keys_btn.clicked.connect(self.get_keys)
        self.keys_btn.setEnabled(False)
        buttons_layout.addWidget(self.keys_btn)
        
        # Кнопка скачивания
        self.download_btn = QPushButton("Скачать видео")
        self.download_btn.clicked.connect(self.download_video)
        self.download_btn.setEnabled(False)
        buttons_layout.addWidget(self.download_btn)
        
        # Кнопка тестирования утилит
        self.test_btn = QPushButton("Тест утилит")
        self.test_btn.clicked.connect(self.test_utilities)
        buttons_layout.addWidget(self.test_btn)
        
        # Кнопка проверки утилит
        check_btn = QPushButton("Проверить утилиты")
        check_btn.clicked.connect(self.check_utilities)
        buttons_layout.addWidget(check_btn)
        
        # Кнопка очистки
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self.clear_all)
        buttons_layout.addWidget(clear_btn)
        
        buttons_layout.addStretch()
        
        # Кнопка выхода
        exit_btn = QPushButton("Выход")
        exit_btn.clicked.connect(self.close)
        buttons_layout.addWidget(exit_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # Статус бар
        self.statusBar().showMessage("Готово")
    
    def apply_styles(self):
        """Применение стилей к виджетам"""
        from .styles import STYLES
        
        self.setStyleSheet(STYLES["main_window"])
        self.centralWidget().setStyleSheet(STYLES["central_widget"])
        
        # Применяем стили к виджетам
        for widget in self.findChildren(QGroupBox):
            widget.setStyleSheet(STYLES["group_box"])
        
        for widget in self.findChildren(QLabel):
            widget.setStyleSheet(STYLES["label"])
        
        for widget in self.findChildren(QLineEdit):
            widget.setStyleSheet(STYLES["line_edit"])
        
        for widget in self.findChildren(QTextEdit):
            widget.setStyleSheet(STYLES["text_edit"])
        
        for widget in self.findChildren(QPushButton):
            widget.setStyleSheet(STYLES["push_button"])
        
        self.progress_bar.setStyleSheet(STYLES["progress_bar"])
        self.quality_combo.setStyleSheet(STYLES["combo_box"])
        self.audio_combo.setStyleSheet(STYLES["combo_box"])
        self.keep_temp_check.setStyleSheet(STYLES["check_box"])
    
    def test_utilities(self):
        """Тестирование работы утилит"""
        self.log("🧪 Тестирование утилит...")
        
        if DOWNLOADER_AVAILABLE and VideoDownloader:
            self.downloader = VideoDownloader(log_callback=self.log)
            success = self.downloader.test_download()
            
            if success:
                self.log("✅ Все утилиты работают корректно", "success")
            else:
                self.log("❌ Проблема с утилитами", "error")
        else:
            self.log("Загрузчик не доступен", "error")
    
    def check_modules_availability(self):
        """Проверка доступности модулей"""
        if not JSON_PARSER_AVAILABLE:
            self.log("Модуль JSONParser не доступен. Парсинг будет эмулирован.", "warning")
        
        if not KEY_FETCHER_AVAILABLE:
            self.log("Модуль KeyFetcher не доступен. Получение ключей будет эмулировано.", "warning")
        
        if not DOWNLOADER_AVAILABLE:
            self.log("Модуль VideoDownloader не доступен. Скачивание будет эмулировано.", "warning")
    
    def check_utilities(self):
        """Проверка наличия необходимых утилит"""
        self.log("Проверка утилит...")
        
        utilities = [
            ("N_m3u8DL-RE", self.config.n_m3u8dl_re),
            ("FFmpeg", self.config.ffmpeg),
        ]
        
        all_found = True
        for name, path in utilities:
            if os.path.exists(path):
                self.log(f"✓ {name} найден: {path}", "success")
            else:
                self.log(f"✗ {name} не найден: {path}", "error")
                all_found = False
        
        if all_found:
            self.log("✅ Все необходимые утилиты найдены!", "success")
        else:
            self.log("❌ Некоторые утилиты не найдены. Разместите их в папке utils/", "error")
    
    def browse_json_file(self):
        """Выбор JSON файла"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите JSON файл",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.json_file_path = file_path
            self.json_path_edit.setText(file_path)
            self.parse_btn.setEnabled(True)
            self.log(f"Файл выбран: {os.path.basename(file_path)}")
    
    def parse_json(self):
        """Парсинг JSON файла"""
        if not self.json_file_path:
            self.log("Ошибка: Файл не выбран", "error")
            return
        
        try:
            self.log("Начало парсинга JSON...")
            
            if JSON_PARSER_AVAILABLE and JSONParser:
                # Реальный парсинг
                result = JSONParser.parse_json_file(self.json_file_path)
                
                if result['success']:
                    # Заполняем поля
                    self.url_edit.setText(result['url'])
                    self.ref_edit.setText(result['referrer'])
                    
                    # M3U8 и MPD URL
                    if result['m3u8_url']:
                        self.m3u8_edit.setText(result['m3u8_url'])
                        self.log(f"M3U8 URL: {result['m3u8_url']}")
                    
                    if result['mpd_url']:
                        self.mpd_edit.setText(result['mpd_url'])
                        self.log(f"MPD URL: {result['mpd_url']}")
                    else:
                        # Создаем MPD из M3U8
                        if result['m3u8_url']:
                            mpd_url = result['m3u8_url'].replace('.m3u8', '.mpd')
                            # Удаляем параметры после .m3u8
                            if '?' in mpd_url:
                                base_url = mpd_url.split('?')[0]
                                mpd_url = base_url
                            self.mpd_edit.setText(mpd_url)
                            self.log(f"Создан MPD URL из M3U8: {mpd_url}")
                        else:
                            self.mpd_edit.setText("URL не найден в JSON")
                            self.log("URL не найден в JSON", "warning")
                    
                    # Видео информация
                    self.video_id_edit.setText(result['video_id'])
                    self.video_title_edit.setText(result['video_title'])
                    
                    # Обновляем список качеств
                    if result['qualities']:
                        self.quality_combo.clear()
                        self.quality_combo.addItems(["Авто"] + result['qualities'])
                        self.log(f"Доступные качества: {', '.join(result['qualities'])}")
                    else:
                        # Попробуем получить качества из заголовков
                        qualities = ["1080p", "720p", "480p", "360p"]
                        self.quality_combo.clear()
                        self.quality_combo.addItems(["Авто"] + qualities)
                        self.log("Качества не найдены в JSON, используем стандартные", "warning")
                    
                    self.log(f"JSON успешно распарсен. Видео: {result['video_title']}")
                    self.log(f"Video ID: {result['video_id']}")
                    
                else:
                    self.log(f"Ошибка парсинга: {result['error']}", "error")
                    return
            else:
                # Эмуляция парсинга
                self.log("Используется эмуляция парсинга (реальный парсер не доступен)", "warning")
                self.url_edit.setText("https://kinescope.io/embed/uzzPPNc45gRqrokozhhPqj")
                self.ref_edit.setText("https://super-effect.ru/")
                
                # Из вашего JSON файла:
                m3u8_url = "https://kinescope.io/e77045a2-8599-4aea-83fc-fd923ef9353e/master.m3u8?expires=1767979636&kinescope_project_id=0f5726cf-9f76-4d38-8793-6ffc51c59462&sign=d3a463e66a30d810bdf2ecce86bcb986&token="
                mpd_url = "https://kinescope.io/e77045a2-8599-4aea-83fc-fd923ef9353e/master.mpd"
                
                self.m3u8_edit.setText(m3u8_url)
                self.mpd_edit.setText(mpd_url)
                self.video_id_edit.setText("e77045a2-8599-4aea-83fc-fd923ef9353e")
                self.video_title_edit.setText("Неформальный семинар (7.0)")
                
                # Обновляем качества
                self.quality_combo.clear()
                self.quality_combo.addItems(["Авто", "1080p", "720p", "480p", "360p"])
                
                self.log("JSON успешно распарсен (тестовые данные)")
                self.log(f"Video ID: e77045a2-8599-4aea-83fc-fd923ef9353e")
                self.log(f"Название: Неформальный семинар (7.0)")
            
            # Активируем кнопки
            self.keys_btn.setEnabled(True)
            self.download_btn.setEnabled(True)
            self.statusBar().showMessage("JSON распарсен успешно")
            
        except Exception as e:
            self.log(f"Ошибка парсинга: {str(e)}", "error")
            self.statusBar().showMessage("Ошибка парсинга")
    
    def get_keys(self):
        """Получение ключей DRM"""
        mpd_url = self.mpd_edit.text().strip()
        referrer = self.ref_edit.text().strip()
        
        if not mpd_url:
            self.log("Ошибка: Не заполнен MPD URL", "error")
            return
        
        if not referrer:
            self.log("Ошибка: Не заполнен Referrer", "error")
            return
        
        # Блокируем кнопки во время получения ключей
        self.keys_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.statusBar().showMessage("Получение ключей...")
        
        if KEY_FETCHER_AVAILABLE and KeyFetcher:
            # Реальное получение ключей с передачей пути к JSON
            try:
                self.key_fetcher = KeyFetcher(log_callback=self.log)
                self.drm_keys = self.key_fetcher.get_keys(
                    mpd_url=mpd_url,
                    referrer=referrer,
                    json_file_path=self.json_file_path
                )
                
                if self.drm_keys:
                    self.log(f"✅ Получено {len(self.drm_keys)} ключей", "success")
                    for key in self.drm_keys:
                        self.log(f"🔑 Ключ: {key}")
                    self.statusBar().showMessage(f"Получено {len(self.drm_keys)} ключей")
                else:
                    self.log("⚠️ Не удалось получить ключи. Попробуйте скачать без них.", "warning")
                    self.statusBar().showMessage("Ключи не получены")
                
            except Exception as e:
                self.log(f"❌ Ошибка получения ключей: {str(e)}", "error")
                self.statusBar().showMessage("Ошибка получения ключей")
        else:
            # Эмуляция получения ключей
            self.log("Начало получения ключей (эмуляция)...", "warning")
            
            # Имитируем процесс получения ключей
            QTimer.singleShot(500, lambda: self.log("Поиск PSSH..."))
            QTimer.singleShot(1000, lambda: self.log("Получение license URL..."))
            QTimer.singleShot(1500, lambda: self.log("Отправка запроса на сервер лицензий..."))
            QTimer.singleShot(2000, lambda: self.finish_key_fetching(True))
        
        # Разблокируем кнопки
        self.keys_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
    
    def finish_key_fetching(self, success=True):
        """Завершение получения ключей"""
        if success:
            self.log("✅ Ключи успешно получены! (эмуляция)", "success")
            self.drm_keys = ["00000000000000000000000000000000:00000000000000000000000000000000"]  # Тестовый ключ
            self.statusBar().showMessage("Ключи получены (эмуляция)")
        else:
            self.log("⚠️ Не удалось получить ключи (эмуляция)", "warning")
            self.statusBar().showMessage("Ключи не получены")
    
    def download_video(self):
        """Скачивание видео"""
        mpd_url = self.mpd_edit.text().strip()
        referrer = self.ref_edit.text().strip()
        quality = self.quality_combo.currentText()
        audio_lang = self.audio_combo.currentText()
        
        if not mpd_url:
            self.log("❌ Ошибка: Не заполнен MPD URL", "error")
            return
        
        if not referrer:
            self.log("❌ Ошибка: Не заполнен Referrer", "error")
            return
        
        # Проверяем, есть ли ключи
        if not hasattr(self, 'drm_keys') or not self.drm_keys:
            reply = QMessageBox.question(
                self,
                'Ключи не получены',
                'Ключи DRM не были получены. Видео будет скачано в зашифрованном виде и не будет воспроизводиться.\n\nПродолжить?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Блокируем кнопки во время скачивания
        self.keys_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.parse_btn.setEnabled(False)
        self.test_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("Скачивание видео...")
        
        if DOWNLOADER_AVAILABLE and VideoDownloader:
            # Реальное скачивание в отдельном потоке
            try:
                self.downloader = VideoDownloader(log_callback=self.log)
                self.download_thread = DownloadThread(
                    downloader=self.downloader,
                    mpd_url=mpd_url,
                    referrer=referrer,
                    quality=quality,
                    audio_lang=audio_lang,
                    drm_keys=self.drm_keys if hasattr(self, 'drm_keys') and self.drm_keys else []
                )
                
                # Подключаем сигналы
                self.download_thread.progress_signal.connect(self.progress_bar.setValue)
                self.download_thread.log_signal.connect(self.log)
                self.download_thread.finished_signal.connect(self.finish_download)
                
                # Запускаем поток
                self.download_thread.start()
                
            except Exception as e:
                self.log(f"❌ Ошибка запуска скачивания: {str(e)}", "error")
                self.unlock_buttons()
                self.statusBar().showMessage("Ошибка скачивания")
        else:
            # Эмуляция скачивания
            self.log("Начало скачивания видео (эмуляция)...", "warning")
            self.simulate_progress()
    
    def simulate_progress(self):
        """Эмуляция прогресса скачивания"""
        self.progress_value = 0
        
        def update_progress():
            if self.progress_value <= 100:
                self.progress_bar.setValue(self.progress_value)
                self.progress_value += 2
                
                if self.progress_value % 20 == 0:
                    self.log(f"Скачивание... {self.progress_value}%")
                
                QTimer.singleShot(50, update_progress)
            else:
                self.finish_download(True)
        
        update_progress()
    
    def finish_download(self, success):
        """Завершение скачивания"""
        if success:
            self.progress_bar.setValue(100)
            self.log("✅ Видео успешно скачано!", "success")
            self.statusBar().showMessage("Видео скачано успешно")
        else:
            self.log("❌ Ошибка при скачивании видео", "error")
            self.statusBar().showMessage("Ошибка скачивания")
        
        # Разблокируем кнопки
        self.unlock_buttons()
        
        # Очистка временных файлов
        if not self.keep_temp_check.isChecked():
            self.cleanup_temp_files()
    
    def cleanup_temp_files(self):
        """Очистка временных файлов"""
        try:
            temp_dir = self.config.temp_dir
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                os.makedirs(temp_dir, exist_ok=True)
                self.log("Временные файлы очищены")
        except Exception as e:
            self.log(f"⚠️ Ошибка очистки временных файлов: {e}", "warning")
    
    def unlock_buttons(self):
        """Разблокировка кнопок"""
        self.keys_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self.parse_btn.setEnabled(True)
        self.test_btn.setEnabled(True)
    
    def clear_all(self):
        """Очистка всех полей"""
        self.json_file_path = None
        self.json_path_edit.clear()
        self.url_edit.clear()
        self.ref_edit.clear()
        self.mpd_edit.clear()
        self.m3u8_edit.clear()
        self.video_id_edit.clear()
        self.video_title_edit.clear()
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # Сбрасываем выпадающие списки
        self.quality_combo.setCurrentIndex(0)
        self.audio_combo.setCurrentIndex(0)
        self.keep_temp_check.setChecked(False)
        
        # Блокируем кнопки
        self.parse_btn.setEnabled(False)
        self.keys_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        
        # Очищаем ключи
        self.drm_keys = None
        
        self.log("Все поля очищены")
        self.statusBar().showMessage("Готово")
    
    def log(self, message: str, level: str = "info"):
        """Добавление сообщения в лог"""
        # Проверяем, что log_text инициализирован
        if self.log_text is None:
            print(f"LOG: {message}")
            return
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if level == "error":
            color = "#ff4444"
            prefix = "[ERROR]"
        elif level == "warning":
            color = "#ffaa00"
            prefix = "[WARN]"
        elif level == "success":
            color = "#44ff44"
            prefix = "[OK]"
        else:
            color = "#aaaaaa"
            prefix = "[INFO]"
        
        html_message = f'<span style="color:{color}">[{timestamp}] {prefix} {message}</span>'
        self.log_text.append(html_message)
        
        # Прокрутка вниз
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Также выводим в консоль для отладки
        print(f"[{prefix}] {message}")
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        # Останавливаем поток скачивания если он запущен
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(
                self,
                'Скачивание в процессе',
                'Скачивание все еще выполняется. Вы уверены, что хотите выйти?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.download_thread.terminate()
                self.download_thread.wait()
                event.accept()
            else:
                event.ignore()
            return
        
        reply = QMessageBox.question(
            self,
            'Подтверждение',
            'Вы уверены, что хотите выйти?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Очищаем временные файлы если не отмечена галочка
            if not self.keep_temp_check.isChecked():
                self.cleanup_temp_files()
            event.accept()
        else:
            event.ignore()