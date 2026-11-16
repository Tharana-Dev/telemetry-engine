from PySide6.QtCore import Qt, Signal, QByteArray, QSize, QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QBrush
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QVBoxLayout, QWidget, QPushButton, QHBoxLayout

from ui.personalization import THEME_PALETTES, ThemePalette, personalization, current_theme
from ui.theme import ThemeColors

_SVGS = {
    "home": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
    "dashboard": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
    "cpu": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3"/></svg>',
    "memory": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 8h20v8H2z"/><path d="M6 16v4M10 16v4M14 16v4M18 16v4"/><path d="M6 4v4M10 4v4M14 4v4M18 4v4"/></svg>',
    "gpu": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="7" cy="12" r="3"/><circle cx="7" cy="12" r="1"/><path d="M12 10h6M12 14h6"/></svg>',
    "disk": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M2 10h20"/><path d="M6 6h.01M6 14h.01"/></svg>',
    "network": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><path d="M5 16v-3a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v3"/><path d="M12 8V2"/></svg>',
    "notifications": '<svg viewBox="0 0 24 24" fill="none" stroke="__COLOR__" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
}

class _SidebarButton(QPushButton):
    def __init__(self, page_id: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page_id = page_id
        self.setToolTip(tooltip)
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._is_active = False
        self._hovered = False
        self.update_visuals()
        
    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.update_visuals()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update_visuals()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update_visuals()
        super().leaveEvent(event)
        
    def update_visuals(self) -> None:
        theme = current_theme()
        if self._is_active:
            color = theme.highlight
            bg = theme.surface
            border_left = f"3px solid {theme.highlight}"
        elif self._hovered:
            color = theme.text
            bg = theme.surface
            border_left = "3px solid transparent"
        else:
            color = theme.text
            bg = "transparent"
            border_left = "3px solid transparent"

        svg_data = _SVGS.get(self.page_id, "").replace("__COLOR__", color)
        renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(24, 24))
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                border: none;
                border-left: {border_left};
                border-radius: 4px;
            }}
        """)

class _ThemeSwatch(QPushButton):
    """A 3-stripe preview block for each theme pack."""
    def __init__(self, palette: ThemePalette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.palette = palette
        self.setFixedSize(36, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Apply {palette.name} Theme")
        self._is_active = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Draw 3 stripes: BG, Text, Highlight
        painter.fillRect(QRectF(0, 0, w/3, h), QColor(self.palette.bg))
        painter.fillRect(QRectF(w/3, 0, w/3, h), QColor(self.palette.text))
        painter.fillRect(QRectF(2*w/3, 0, w/3, h), QColor(self.palette.highlight))
        
        # Draw border
        border_color = QColor(current_theme().text) if self._is_active else QColor(current_theme().border)
        pen = painter.pen()
        pen.setColor(border_color)
        pen.setWidth(2 if self._is_active else 1)
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(0, 0, w, h), 4, 4)

    def set_active(self, active: bool):
        self._is_active = active
        self.update()

class Sidebar(QWidget):
    page_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(64)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 24, 8, 24)
        layout.setSpacing(12)

        nav_items = [
            ("home", "Home"), ("dashboard", "Overview"), ("cpu", "CPU"),
            ("memory", "Memory"), ("gpu", "GPU"), ("disk", "Disk"), ("network", "Network"),("notifications", "Notifications")
        ]

        self._nav_buttons = {}
        for page_id, label in nav_items:
            btn = _SidebarButton(page_id, label, self)
            btn.clicked.connect(lambda checked=False, p=page_id: self.page_requested.emit(p))
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._nav_buttons[page_id] = btn

        layout.addStretch()

        # --- Theme Swatches ---
        accent_layout = QVBoxLayout()
        accent_layout.setSpacing(10)
        accent_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        self._swatches = []
        for idx, palette in enumerate(THEME_PALETTES):
            swatch = _ThemeSwatch(palette, self)
            swatch.clicked.connect(lambda checked=False, i=idx: personalization().set_theme_index(i))
            accent_layout.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignHCenter)
            self._swatches.append(swatch)
            
        layout.addLayout(accent_layout)
        
        self.refresh_theme()
        self.set_active_page("home")

    def set_active_page(self, page_id: str) -> None:
        for pid, btn in self._nav_buttons.items():
            btn.set_active(pid == page_id)

    def refresh_theme(self) -> None:
        # Update sidebar background
        theme = current_theme()
        self.setStyleSheet(f"""
            Sidebar {{
                background-color: {theme.bg};
                border-right: 1px solid {theme.border};
            }}
        """)
        
        # Update active icons
        for btn in self._nav_buttons.values():
            btn.update_visuals()
            
        # Update swatches
        active_idx = personalization().theme_index
        for i, swatch in enumerate(self._swatches):
            swatch.set_active(i == active_idx)