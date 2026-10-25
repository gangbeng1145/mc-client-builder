# -*- coding: utf-8 -*-
"""界面配色与样式表。"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication
import sys

BG = "#0f1117"
PANEL = "#161922"
CARD = "#1c202b"
CARD_HOVER = "#232838"
BORDER = "#2a3040"
TEXT = "#e8ebf3"
MUTED = "#8b93a8"
ACCENT = "#4c8dff"
ACCENT2 = "#7a5cff"
GREEN = "#3ecf8e"
RED = "#ff6b6b"
YELLOW = "#f5b84d"

QSS = f"""
QWidget {{
    color: {TEXT};
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}}
QWidget#Root {{
    background-color: {BG};
}}
QFrame#Card {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#AppTitle {{
    font-size: 17px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#AppSub {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#SectionTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#FieldLabel {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#Hint {{
    color: {MUTED};
    font-size: 11px;
}}
QLabel#Stage {{
    color: {ACCENT};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#Success {{
    color: {GREEN};
}}
QLabel#Error {{
    color: {RED};
}}

QLineEdit, QComboBox {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    outline: none;
}}
QPushButton {{
    background-color: {CARD_HOVER};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: #2b3245;
    border-color: #3a435c;
}}
QPushButton:pressed {{
    background-color: #262c3d;
}}
QPushButton:disabled {{
    color: #5d6478;
    background-color: #1a1d26;
    border-color: #242a38;
}}
QPushButton#Primary {{
    background-color: {ACCENT};
    border: none;
    border-radius: 11px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 700;
    color: white;
}}
QPushButton#Primary:hover {{
    background-color: #5d99ff;
}}
QPushButton#Primary:disabled {{
    background-color: #2a3550;
    color: #7c879e;
}}
QPushButton#Ghost {{
    background-color: transparent;
    border: 1px solid {BORDER};
}}
QPushButton#Ghost:hover {{
    background-color: {CARD_HOVER};
}}
QPushButton#Chip {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 12px;
    color: {MUTED};
}}
QPushButton#Chip:hover {{
    background-color: {CARD_HOVER};
    color: {TEXT};
}}
QPushButton#Chip:checked {{
    background-color: {ACCENT};
    color: white;
    font-weight: 600;
}}

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListView {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QPlainTextEdit {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: #b9c1d4;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    padding: 6px;
}}

QProgressBar {{
    background-color: {PANEL};
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 6px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT2});
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #333a4d;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #414a63;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    height: 10px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: #333a4d;
    border-radius: 4px;
}}
QCheckBox {{
    color: {TEXT};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 5px;
    border: 1px solid {BORDER};
    background: {PANEL};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QToolTip {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 6px;
}}
QMessageBox {{
    background-color: {CARD};
}}
QMenu {{
    background-color: {CARD};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background-color: {ACCENT};
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    _load_windows_fonts()
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(BG))
    pal.setColor(QPalette.WindowText, QColor(TEXT))
    pal.setColor(QPalette.Base, QColor(PANEL))
    pal.setColor(QPalette.AlternateBase, QColor(CARD))
    pal.setColor(QPalette.Text, QColor(TEXT))
    pal.setColor(QPalette.Button, QColor(CARD))
    pal.setColor(QPalette.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ToolTipBase, QColor(CARD))
    pal.setColor(QPalette.ToolTipText, QColor(TEXT))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)


def _load_windows_fonts() -> None:
    if sys.platform != "win32":
        return
    for name in ("msyh.ttc", "msyhbd.ttc", "msyhl.ttc", "segoeui.ttf",
                 "seguisb.ttf", "consola.ttf", "consolab.ttf"):
        path = f"C:/Windows/Fonts/{name}"
        try:
            QFontDatabase.addApplicationFont(path)
        except Exception:
            pass
