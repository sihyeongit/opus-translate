"""Transparent always-on-top subtitle overlay (PyQt6).

Renders up to two rolling subtitle slots:
  - Optional EN line (smaller, gray)
  - KO line (large, white with black outline)

The window is frameless, translucent, always-on-top, and click-through so
it never steals focus from the underlying video/app.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QWidget

log = logging.getLogger(__name__)


class LangMode(Enum):
    KO_ONLY = "ko"
    EN_KO = "en_ko"


@dataclass
class Caption:
    en: str
    ko: str


class SubtitleOverlay(QWidget):
    captionReceived = pyqtSignal(object)

    def __init__(
        self,
        font_family: str = "Malgun Gothic",
        ko_font_size: int = 28,
        en_font_size: int = 18,
        bottom_margin_px: int = 80,
        width_ratio: float = 0.8,
        max_captions: int = 2,
    ):
        super().__init__()
        self._font_family = font_family
        self._ko_size = ko_font_size
        self._en_size = en_font_size
        self._bottom_margin = bottom_margin_px
        self._width_ratio = width_ratio
        self._lang_mode = LangMode.EN_KO
        self._captions: Deque[Caption] = deque(maxlen=max_captions)
        self._visible = True

        self._configure_window()
        self._position_window()
        self.captionReceived.connect(self._on_caption)

    def _configure_window(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _position_window(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        width = int(screen.width() * self._width_ratio)
        height = 220
        x = (screen.width() - width) // 2
        y = screen.height() - height - self._bottom_margin
        self.setGeometry(x, y, width, height)

    @pyqtSlot(object)
    def _on_caption(self, caption: Caption) -> None:
        self._captions.append(caption)
        self.update()

    def push_caption(self, en: str, ko: str) -> None:
        """Thread-safe entry point for pipeline workers."""
        self.captionReceived.emit(Caption(en=en, ko=ko))

    def toggle_visible(self) -> None:
        self._visible = not self._visible
        self.setVisible(self._visible)

    def cycle_lang_mode(self) -> None:
        self._lang_mode = (
            LangMode.KO_ONLY if self._lang_mode == LangMode.EN_KO else LangMode.EN_KO
        )
        self.update()

    def paintEvent(self, event) -> None:
        if not self._captions:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        y = rect.height() - 10

        for caption in reversed(self._captions):
            y = self._draw_caption(painter, caption, y)
            y -= 12
            if y < 0:
                break

    def _draw_caption(self, painter: QPainter, caption: Caption, y_bottom: int) -> int:
        rect_width = self.rect().width()

        if caption.ko:
            y_bottom = self._draw_line(
                painter,
                caption.ko,
                y_bottom,
                size=self._ko_size,
                fill=QColor(255, 255, 255, 240),
                outline=QColor(0, 0, 0, 230),
                bold=True,
                max_width=rect_width,
            )
        if self._lang_mode == LangMode.EN_KO and caption.en:
            y_bottom -= 4
            y_bottom = self._draw_line(
                painter,
                caption.en,
                y_bottom,
                size=self._en_size,
                fill=QColor(200, 200, 200, 220),
                outline=QColor(0, 0, 0, 200),
                bold=False,
                max_width=rect_width,
            )
        return y_bottom

    def _draw_line(
        self,
        painter: QPainter,
        text: str,
        y_bottom: int,
        size: int,
        fill: QColor,
        outline: QColor,
        bold: bool,
        max_width: int,
    ) -> int:
        font = QFont(self._font_family, size)
        font.setBold(bold)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        lines = self._wrap(text, metrics, max_width - 40)
        line_height = metrics.height() + 4

        for line in reversed(lines):
            width = metrics.horizontalAdvance(line)
            x = (max_width - width) // 2
            y = y_bottom

            path = QPainterPath()
            path.addText(x, y, font, line)
            painter.setPen(QPen(outline, 4))
            painter.drawPath(path)
            painter.fillPath(path, fill)

            y_bottom -= line_height
        return y_bottom

    @staticmethod
    def _wrap(text: str, metrics: QFontMetrics, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return []
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = current + " " + word
            if metrics.horizontalAdvance(trial) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines
