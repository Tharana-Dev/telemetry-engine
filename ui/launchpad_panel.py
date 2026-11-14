import math
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
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
        self.setMinimumHeight(120)
        self.setMaximumHeight(160)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(30) # ~33 FPS for smooth animation

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
            # Combine two sine waves for a complex, organic "breathing" motion
            val1 = math.sin(self.time + i * 0.3)
            val2 = math.sin(self.time * 0.6 + i * 0.15)
            
            # Normalize the value between 0.1 and 1.0 so bars don't disappear
            normalized = (val1 + val2 + 2) / 4
            bar_height = height * (0.15 + (normalized * 0.85))
            
            x = i * bar_width + spacing / 2
            y = height - bar_height
            
            # Fade the edges of the wave
            edge_dist = abs((num_bars / 2) - i) / (num_bars / 2)
            alpha = int(255 * (1 - edge_dist ** 2))
            
            painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), alpha))
            
            # Draw the vertical bar
            rect = QRectF(x, y, bar_width - spacing, bar_height)
            painter.drawRoundedRect(rect, 3, 3)


class LaunchpadPanel(QWidget):
    """Right-hand launchpad showing WinTmp admin status and the HUD."""

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
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(4)
        hero_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Massive Clock
        self._clock_lbl = QLabel("00:00:00", hero_box)
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 2. The Date
        self._date_lbl = QLabel("SYSTEM DATE", hero_box)
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_lbl.setStyleSheet(f"""
            color: {ThemeColors.TEXT_SECONDARY};
            font-family: {ThemeFonts.FAMILY_UI};
            font-size: {ThemeFonts.SIZE_BODY}px;
            font-weight: 600;
            letter-spacing: 2px;
            border: none;
        """)

        # 3. Status Label
        self._status_lbl = QLabel("● SYSTEM ONLINE", hero_box)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"""
            color: {ThemeColors.STATUS_OK};
            font-family: {ThemeFonts.FAMILY_MONO};
            font-size: {ThemeFonts.SIZE_CAPTION}px;
            font-weight: 700;
            letter-spacing: 1px;
            margin-top: 4px;
            border: none;
        """)

        hero_layout.addWidget(self._clock_lbl)
        hero_layout.addWidget(self._date_lbl)
        hero_layout.addWidget(self._status_lbl)
        
        hero_layout.addSpacing(16)

        # 4. The Ambient Wave
        self._wave = AmbientWaveWidget(hero_box)
        hero_layout.addWidget(self._wave)
        
        parent_layout.addWidget(hero_box)

        # 5. Start the clock
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000) 
        self._update_clock() 
        
        self.refresh_accent()

    def _update_clock(self) -> None:
        now = datetime.now()
        self._clock_lbl.setText(now.strftime("%H:%M:%S"))
        self._date_lbl.setText(now.strftime("%A, %b %d %Y").upper())

    def refresh_accent(self) -> None:
        """Updates the clock and wave colors when accent changes."""
        if hasattr(self, "_clock_lbl"):
            self._clock_lbl.setStyleSheet(f"""
                color: {current_accent().primary};
                font-family: {ThemeFonts.FAMILY_MONO};
                font-size: 72px;
                font-weight: 900;
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