"""
Точка входа в приложение Kinescope Downloader
"""
import sys
import os

# Самый простой вариант запуска
from PyQt5.QtWidgets import QApplication

# Добавляем путь к корневой директории
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def main():
    """Основная функция приложения"""
    app = QApplication(sys.argv)
    app.setApplicationName("Kinescope Downloader")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()