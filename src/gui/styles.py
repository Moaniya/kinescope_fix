"""
Стили для графического интерфейса
"""

STYLES = {
    "main_window": """
        QMainWindow {
            background-color: #2b2b2b;
        }
    """,
    
    "central_widget": """
        QWidget {
            background-color: #2b2b2b;
        }
    """,
    
    "group_box": """
        QGroupBox {
            color: #ffffff;
            font-size: 13px;
            font-weight: bold;
            border: 2px solid #3c3c3c;
            border-radius: 6px;
            margin-top: 4px;
            margin-bottom: 4px;
            padding-top: 10px;
            padding-left: 6px;
            padding-right: 6px;
            padding-bottom: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
    """,
    
    "label": """
        QLabel {
            color: #ffffff;
            font-size: 11px;
            padding: 1px;
        }
    """,
    
    "line_edit": """
        QLineEdit {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px 6px;
            font-size: 11px;
        }
        QLineEdit:focus {
            border: 1px solid #0078d7;
        }
        QLineEdit:read-only {
            background-color: #353535;
            color: #bbbbbb;
        }
    """,
    
    "text_edit": """
        QTextEdit {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 4px;
            font-size: 10px;
            font-family: 'Consolas', 'Courier New', monospace;
            padding: 3px;
        }
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 10px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 4px;
            min-height: 15px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #666666;
        }
    """,
    
    "push_button": """
        QPushButton {
            background-color: #0078d7;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 11px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #404040;
            color: #777777;
        }
    """,
    
    "progress_bar": """
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 4px;
            text-align: center;
            color: white;
            font-size: 10px;
            font-weight: bold;
            background-color: #353535;
            height: 18px;
        }
        QProgressBar::chunk {
            background-color: #0078d7;
            border-radius: 4px;
        }
    """,
    
    "combo_box": """
        QComboBox {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px 6px;
            font-size: 11px;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid white;
        }
        QComboBox QAbstractItemView {
            background-color: #3c3c3c;
            color: white;
            selection-background-color: #0078d7;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 3px;
        }
        QComboBox QAbstractItemView::item {
            min-height: 20px;
            padding: 3px 6px;
        }
    """,
    
    "check_box": """
        QCheckBox {
            color: #ffffff;
            font-size: 11px;
            spacing: 6px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QCheckBox::indicator:unchecked {
            border: 1px solid #555555;
            background-color: #3c3c3c;
            border-radius: 2px;
        }
        QCheckBox::indicator:checked {
            border: 1px solid #0078d7;
            background-color: #0078d7;
            border-radius: 2px;
        }
        QCheckBox::indicator:checked:hover {
            border: 1px solid #106ebe;
            background-color: #106ebe;
        }
    """
}