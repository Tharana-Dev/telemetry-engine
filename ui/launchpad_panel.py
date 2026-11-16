import math
from datetime import datetime

from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.personalization import current_theme, greeting_for_now
from ui.system_probe import SystemProfile
from ui.theme import ThemeFonts


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
        
        # Use the theme's highlight color for the wave
        accent = QColor(current_theme().highlight)
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
        
        self.refresh_theme()

    def _init_header(self, parent_layout: QVBoxLayout) -> None:
        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self._greeting_lbl = QLabel("System Telemetry", self)
        self._greeting_lbl.setStyleSheet(
            f"color: {current_theme().text};"
            f"font-size: {ThemeFonts.SIZE_HERO}px;"
            "font-weight: 700;"
            "border: none;"
        )

        self._subtitle_lbl = QLabel(
            "Jump directly to a hardware sector or open the full live monitor.",
            self,
        )
        self._subtitle_lbl.setWordWrap(True)
        self._subtitle_lbl.setStyleSheet(
            f"color: {current_theme().text};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "border: none;"
        )

        text_col.addWidget(self._greeting_lbl)
        text_col.addWidget(self._subtitle_lbl)
        parent_layout.addLayout(text_col)

    def _init_admin_card(self, parent_layout: QVBoxLayout) -> None:
        self._admin_card = QFrame(self)
        self._admin_card.setObjectName("AdminCard")
        self._admin_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        card_layout = QHBoxLayout(self._admin_card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        self._admin_title = QLabel("Checking Privileges...", self._admin_card)
        
        self._admin_desc = QLabel("", self._admin_card)
        self._admin_desc.setWordWrap(True)

        text_col.addWidget(self._admin_title)
        text_col.addWidget(self._admin_desc)

        self._elevate_btn = QPushButton("Restart as Admin", self._admin_card)
        self._elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._elevate_btn.clicked.connect(self.restart_admin_requested.emit)

        card_layout.addLayout(text_col, 1)
        card_layout.addWidget(self._elevate_btn)
        parent_layout.addWidget(self._admin_card)


    def _init_hero_panel(self, parent_layout: QVBoxLayout) -> None:
        self._hero_box = QFrame(self)
        
        hero_layout = QVBoxLayout(self._hero_box)
        hero_layout.setContentsMargins(32, 24, 32, 24)
        hero_layout.setSpacing(8)

        # Title
        self._about_title = QLabel("ABOUT & SYSTEM GUIDE", self._hero_box)
        hero_layout.addWidget(self._about_title)

        self._section_headings: list[QLabel] = []
        self._section_bodies: list[QLabel] = []

        # Helper to create a section block
        def create_section(heading: str, body_html: str) -> QLabel:
            w = QWidget(self._hero_box)
            w.setStyleSheet("border: none; background: transparent;")
            l = QVBoxLayout(w)
            l.setContentsMargins(0, 8, 0, 8) 
            l.setSpacing(4) 
            
            h = QLabel(heading, w)
            self._section_headings.append(h)
            
            t = QLabel(body_html, w)
            t.setWordWrap(True)
            t.setOpenExternalLinks(True) 
            self._section_bodies.append(t)
            
            l.addWidget(h)
            l.addWidget(t)
            hero_layout.addWidget(w)
            return t

        create_section(
            "📊 How to read the Graphs",
            "Graphs display data over the last 60 seconds. The X-Axis shows negative time "
            "(e.g., -30s means '30 seconds ago'). 0s represents real-time 'Right Now'."
        )
        create_section(
            "❓ What does '--' mean?",
            "If a metric shows '--', the sensor is unavailable. This usually happens if the app "
            "lacks <b>Administrator privileges</b>, or the hardware driver does not support it."
        )
        create_section(
            "⚠️ Known Limitations",
            "• <b>CPU Temps</b>: Windows blocks raw MSR reads without Admin rights (WinTmp).<br>"
            "• <b>GPU Utilization</b>: NVIDIA Optimus may route workloads to the iGPU, showing 0% on the dGPU.<br>"
            "• <b>Fan Speeds</b>: Most laptops control fans via the EC, which is often hidden from software."
        )
        create_section(
            "🚀 Upcoming Versions (Roadmap)",
            "• <b>v1.2.x</b>: Process Explorer & Custom Alerts<br>"
            "• <b>v1.3.x</b>: Historical Data Logging (SQLite) & Plugin System"
        )
        self._dev_body = create_section("👨‍💻 Developer", "")

        hero_layout.addStretch()

        self._wave = AmbientWaveWidget(self._hero_box)
        hero_layout.addWidget(self._wave)
        
        parent_layout.addWidget(self._hero_box)


    def refresh_theme(self) -> None:
        """Updates all QSS dynamically when the theme changes."""
        theme = current_theme()

        # 1. Header Text
        self._greeting_lbl.setStyleSheet(
            f"color: {theme.text};"
            f"font-size: {ThemeFonts.SIZE_HERO}px;"
            "font-weight: 700;"
            "border: none;"
        )
        self._subtitle_lbl.setStyleSheet(
            f"color: {theme.text};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "border: none;"
        )

        # 2. Admin Card
        self._admin_card.setStyleSheet(
            f"QFrame#AdminCard {{ background-color: {theme.surface};"
            f"border: 1px solid {theme.highlight}; border-radius: 8px; }}"
        )
        self._admin_title.setStyleSheet(
            f"color: {theme.highlight};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 700;"
            "border: none;"
        )
        self._admin_desc.setStyleSheet(
            f"color: {theme.text};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "border: none;"
        )
        self._elevate_btn.setStyleSheet(
            f"background-color: {theme.highlight};"
            f"color: {theme.bg};"
            "border: none; border-radius: 6px; padding: 6px 12px;"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 700;"
        )

         # 3. Hero Panel & Guide Sections
        self._hero_box.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 12px;
            }}
        """)
        self._about_title.setStyleSheet(f"""
            color: {theme.highlight};
            font-family: {ThemeFonts.FAMILY_MONO};
            font-size: 18px;
            font-weight: 900;
            letter-spacing: 2px;
            border: none;
        """)

        for h in self._section_headings:
            h.setStyleSheet(
                f"color: {theme.highlight}; font-size: 15px; font-weight: 700; border: none;"
            )

        for t in self._section_bodies:
            t.setStyleSheet(
                f"color: {theme.text}; font-size: 14px; line-height: 1.5; border: none;"
            )

        link_style = f"style='color: {theme.highlight}; text-decoration: none; font-weight: bold;'"
        self._dev_body.setText(
            f"Created by <b>Tharana Nimsara</b><br>"
            f"<a href='https://github.com' {link_style}>GitHub</a> &nbsp;|&nbsp; "
            f"<a href='https://vercel.app' {link_style}>Website</a>"
        )

         # 4. Ambient Wave
        if hasattr(self, "_wave"):
            self._wave.update()

    def update_profile(self, profile: SystemProfile) -> None:
        """Updates greeting and WinTmp admin banner."""
        theme = current_theme()
        
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
                f"QFrame#AdminCard {{ background-color: {theme.surface};"
                f"border: 1px solid {theme.highlight}; border-radius: 8px; }}"
            )
            self._admin_title.setText("● All sensors unlocked")
            self._admin_title.setStyleSheet(
                f"color: {theme.highlight};"
                f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 700;"
            )
            self._admin_desc.setText(
                "You're running with full WinTmp access — temperatures "
                "and fan RPMs are live."
            )
            self._elevate_btn.setVisible(False)
        else:
            self._admin_card.setStyleSheet(
                f"QFrame#AdminCard {{ background-color: {theme.surface};"
                f"border: 1px solid {theme.highlight}; border-radius: 8px; }}"
            )
            self._admin_title.setText("▲ Unlock full sensor access")
            self._admin_title.setStyleSheet(
                f"color: {theme.highlight};"
                f"font-size: {ThemeFonts.SIZE_BODY}px; font-weight: 700;"
            )
            self._admin_desc.setText(
                "Grant Administrator rights to unlock WinTmp CPU/board "
                "thermals and fan RPMs."
            )
            self._elevate_btn.setVisible(True)