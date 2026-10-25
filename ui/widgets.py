# -*- coding: utf-8 -*-
"""自定义控件：标题栏、卡片、版本列表（自绘）。"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QAbstractListModel, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from . import theme


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 12, 10)
        lay.setSpacing(10)

        logo = QLabel("MC")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(34, 34)
        logo.setStyleSheet(
            f"background-color: {theme.ACCENT}; color: white; border-radius: 10px;"
            f"font-weight: 800; font-size: 13px;"
        )
        lay.addWidget(logo)

        titles = QVBoxLayout()
        titles.setSpacing(1)
        t = QLabel("MC 客户端构建器")
        t.setObjectName("AppTitle")
        s = QLabel("下载 · 配置 · 打包，成品可直接被 HMCL 启动")
        s.setObjectName("AppSub")
        titles.addWidget(t)
        titles.addWidget(s)
        lay.addLayout(titles)
        lay.addStretch(1)

        for text, tip, slot in (
            ("—", "最小化", self._min),
            ("□", "最大化", self._max),
            ("✕", "关闭", self._close),
        ):
            b = QLabel(text)
            b.setToolTip(tip)
            b.setAlignment(Qt.AlignCenter)
            b.setFixedSize(34, 30)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QLabel { color: #8b93a8; border-radius: 8px; font-size: 14px; }"
                "QLabel:hover { background-color: #232838; color: #e8ebf3; }"
            )
            b.mousePressEvent = (lambda _e, f=slot: f())
            lay.addWidget(b)

    def _min(self):
        self.window().showMinimized()

    def _max(self):
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()

    def _close(self):
        self.window().close()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        self._max()


class Card(QFrame):
    def __init__(self, title: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(16, 14, 16, 14)
        self._lay.setSpacing(10)
        if title:
            label = QLabel(title)
            label.setObjectName("SectionTitle")
            self._lay.addWidget(label)

    def body(self) -> QVBoxLayout:
        return self._lay


class VersionModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=None) -> int:
        return 0 if parent and parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        if role == Qt.DisplayRole:
            return row.get("id")
        if role == Qt.UserRole:
            return row
        return None


TYPE_COLORS = {
    "release": theme.GREEN,
    "snapshot": theme.YELLOW,
    "old_beta": theme.MUTED,
    "old_alpha": theme.MUTED,
}
TYPE_NAMES = {
    "release": "正式版",
    "snapshot": "快照",
    "old_beta": "远古 Beta",
    "old_alpha": "远古 Alpha",
}


class VersionDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        return QSize(0, 58)

    def paint(self, painter: QPainter, option, index) -> None:
        row = index.data(Qt.UserRole) or {}
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        r = QRectF(option.rect.adjusted(4, 2, -4, -2))
        selected = bool(option.state & QStyle.State_Selected)
        hover = bool(option.state & QStyle.State_MouseOver)

        if selected:
            bg = QColor(theme.ACCENT)
            bg.setAlpha(40)
            border = QColor(theme.ACCENT)
            border.setAlpha(130)
        elif hover:
            bg = QColor(theme.CARD_HOVER)
            border = QColor(0, 0, 0, 0)
        else:
            bg = QColor(0, 0, 0, 0)
            border = QColor(0, 0, 0, 0)

        painter.setBrush(bg)
        painter.setPen(QPen(border, 1) if border.alpha() else Qt.NoPen)
        painter.drawRoundedRect(r, 10, 10)

        f = QFont(painter.font())
        f.setPointSizeF(10.5)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(
            r.adjusted(12, 7, -86, 0), Qt.AlignLeft | Qt.AlignTop,
            str(row.get("id", "")),
        )

        f.setPointSizeF(8.5)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(QColor(theme.MUTED))
        date = str(row.get("releaseTime") or row.get("time") or "")[:10]
        painter.drawText(
            r.adjusted(12, 0, -86, -8), Qt.AlignLeft | Qt.AlignBottom,
            f"{TYPE_NAMES.get(row.get('type'), row.get('type') or '')}   {date}",
        )

        badge_color = QColor(TYPE_COLORS.get(row.get("type"), theme.MUTED))
        text = "快照" if row.get("type") == "snapshot" else ("正式" if row.get("type") == "release" else "远古")
        bw, bh = 40, 20
        br = QRectF(r.right() - bw - 10, r.center().y() - bh / 2, bw, bh)
        badge_bg = QColor(badge_color)
        badge_bg.setAlpha(30)
        painter.setPen(Qt.NoPen)
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(br, 6, 6)
        painter.setPen(badge_color)
        f.setPointSizeF(8)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(br, Qt.AlignCenter, text)
        painter.restore()


class VersionList(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(VersionDelegate(self))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
