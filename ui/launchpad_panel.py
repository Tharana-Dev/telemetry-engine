from datetime import datetime
import math

from PySide6.QtCore import Qt, Signal, QTimer, QRectF  # <-- FIXED: Added QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.personalization import current_accent, greeting_for_now
from ui.system_probe import SystemProfile
from ui.theme import ThemeColors, ThemeFonts


class AmbientWaveWidget(QWidget):
    """A smooth, glowing waveform that breathes across the screen."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.time = 0.0
        self.setFixedHeight(80)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30)

    def _tick(self):
        self.time += 0.08
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        accent = QColor(current_accent().primary)
        painter.setPen(Qt.PenStyle.NoPen)
        
        width = self.width()
        height = self.height()
        num_bars = 40
        bar_width = width / num_bars
        spacing = 4
        
        for i in range(num_bars):
            val1 = math.sin(self.time + i * 0.3)
            val2 = math.sin(self.time * 0.6 + i * 0.15)
            normalized = (val1 + val2 + 2) / 4
            bar_height = height * (0.15 + (normalized * 0.85))
            
            x = i * bar_width + spacing / 2
            y = height - bar_height
            
            edge_dist = abs((num_bars / 2) - i) / (num_bars / 2)
            alpha = int(255 * (1 - edge_dist ** 2))
            
            painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), alpha))
            rect = QRectF(x, y, bar_width - spacing, bar_height)
            painter.drawRoundedRect(rect, 3, 3)


class LaunchpadPanel(QWidget):
    """Right-hand launchpad showing WinTmp admin status and App Guide."""

    start_requested = Signal(str, bool)
    restart_admin_requested = Signal()

    def __init__(
        self, profile: SystemProfile | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self._init_header(layout)
        self._init_admin_card(layout)
        
        layout.addStretch()
        
        self._init_hero_panel(layout)

        if profile is not None:
            self.update_profile(profile)

    def _init_header(self, parent_layout: QVBoxLayout) -> None:
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self._greeting_lbl = QLabel("System Telemetry", self)
        self._greeting_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY};"
            f"font-size: {ThemeFonts.SIZE_HERO}px;"
            "font-weight: 700;"
        )

        self._subtitle_lbl = QLabel(
            "Jump directly to a hardware sector or open the full live monitor.",
            self,
        )
        self._subtitle_lbl.setWordWrap(True)
        self._subtitle_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
        )

        text_col.addWidget(self._greeting_lbl)
        text_col.addWidget(self._subtitle_lbl)
        parent_layout.addLayout(text_col)

    def _init_admin_card(self, parent_layout: QVBoxLayout) -> None:
        self._admin_card = QFrame(self)
        self._admin_card.setObjectName("AdminCard")

        card_layout = QHBoxLayout(self._admin_card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._admin_title = QLabel("Checking Privileges...", self._admin_card)
        self._admin_title.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 700; border: none;"
        )

        self._admin_desc = QLabel("", self._admin_card)
        self._admin_desc.setWordWrap(True)
        self._admin_desc.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "border: none;"
        )

        text_col.addWidget(self._admin_title)
        text_col.addWidget(self._admin_desc)

        self._elevate_btn = QPushButton("Restart as Admin", self._admin_card)
        self._elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._elevate_btn.setStyleSheet(
            f"background-color: {ThemeColors.STATUS_WARN};"
            f"color: {ThemeColors.BG_BASE};"
            "border: none;"
            "border-radius: 6px;"
            "padding: 6px 12px;"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 700;"
        )
        self._elevate_btn.clicked.connect(self.restart_admin_requested.emit)

        card_layout.addLayout(text_col, 1)
        card_layout.addWidget(self._elevate_btn)
        parent_layout.addWidget(self._admin_card)

    def _init_hero_panel(self, parent_layout: QVBoxLayout) -> None:
        hero_box = QFrame(self)
        hero_box.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_BASE};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 12px;
            }}
        """)
        
        hero_layout = QVBoxLayout(hero_box)
        hero_layout.setContentsMargins(32, 24, 32, 24)
        hero_layout.setSpacing(12)

        # Title
        title = QLabel("ABOUT & SYSTEM GUIDE", hero_box)
        title.setStyleSheet(f"""
            color: {current_accent().primary};
            font-family: {ThemeFonts.FAMILY_MONO};
            font-size: 18px;
            font-weight: 900;
            letter-spacing: 2px;
            border: none;
        """)
        self._about_title = title
        hero_layout.addWidget(title)

        # Guide Text Blocks
        def create_guide_block(heading: str, text: str) -> QWidget:
            w = QWidget(hero_box)
            w.setStyleSheet("border: none; background: transparent;")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 8, 0, 8)
            l.setSpacing(4)
            
            h = QLabel(heading, w)
            h.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-size: 14px; font-weight: 700; border: none;")
            t = QLabel(text, w)
            t.setWordWrap(True)
            t.setStyleSheet(f"color: {ThemeColors.TEXT_SECONDARY}; font-size: 13px; line-height: 1.4; border: none;")
            
            l.addWidget(h)
            l.addWidget(t)
            return w

        hero_layout.addWidget(create_guide_block(
            "1. What is Telemetry Mission Control?",
            "A high-performance system monitor built with PySide6 and psutil. "
            "It provides live, hardware-level telemetry with a dynamic, customizable UI."
        ))

        hero_layout.addWidget(create_guide_block(
            "2. How to read the Graphs",
            "Graphs display data over the last 60 seconds. The X-Axis shows negative time "
            "(e.g., -30s means '30 seconds ago'). 0s represents real-time 'Right Now'."
        ))

        hero_layout.addWidget(create_guide_block(
            "3. What does '--' mean?",
            "If a metric shows '--', it means the sensor is unavailable. This happens if "
            "the app lacks Administrator privileges, or the hardware driver does not support it."
        ))

        hero_layout.addStretch()

        self._wave = AmbientWaveWidget(hero_box)
        hero_layout.addWidget(self._wave)
        
        parent_layout.addWidget(hero_box)
        self.refresh_accent()

    def refresh_accent(self) -> None:
        if hasattr(self, "_about_title"):
            self._about_title.setStyleSheet(f"""
                color: {current_accent().primary};
                font-family: {ThemeFonts.FAMILY_MONO};
                font-size: 18px;
                font-weight: 900;
                letter-spacing: 2px;
                border: none;
            """)
        if hasattr(self, "_wave"):
            self._wave.update()

    def update_profile(self, profile: SystemProfile) -> None:
        device_word = profile.device_type.label.split()[0].lower()
        if device_word == "unknown":
            device_word = "system"

        self._greeting_lbl.setText(f"{greeting_for_now()}, {profile.username}")
        self._subtitle_lbl.setText(
            f"Your {device_word} is ready — jump into a live sector "
            f"or open the full monitor."
        )

        if profile.is_admin:
            self._admin_card.setStyleSheet(
                f"QFrame#AdminCard {{ background-color: {ThemeColors.BG_SURFACE};"
                f"border: 1px solid {ThemeColors.STATUS_OK}; border-radius: 8px; }}"
            )
            self._admin_title.setText("● All sensors unlocked")
            self._admin_title.setStyleSheet(
                f"color: {ThemeColors.STATUS_OK};"
                f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 700;"
            )
            self._admin_desc.setText(
                "You're running with full WinTmp access — temperatures "
                "and fan RPMs are live."
            )
            self._elevate_btn.setVisible(False)
        else:
            self._admin_card.setStyleSheet(
                f"QFrame#AdminCard {{ background-color: {ThemeColors.BG_SURFACE};"
                f"border: 1px solid {ThemeColors.STATUS_WARN}; border-radius: 8px; }}"
            )
            self._admin_title.setText("▲ Unlock full sensor access")
            self._admin_title.setStyleSheet(
                f"color: {ThemeColors.STATUS_WARN};"
                f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 700;"
            )
            self._admin_desc.setText(
                "Grant Administrator rights to unlock WinTmp CPU/board "
                "thermals and fan RPMs."
            )
            self._elevate_btn.setVisible(True)