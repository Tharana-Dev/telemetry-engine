from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget

from ui.personalization import current_theme
from ui.theme import ThemeFonts
from ui.system_probe import SystemProfile


class SystemBanner(QFrame):
    """A wide status bar at the bottom of the Dashboard."""
    
    def __init__(self, profile: SystemProfile, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._profile = profile

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(24)

        # Helper to create a data block
        def create_block(title: str, value: str, color: str | None = None):
            box = QVBoxLayout()
            box.setSpacing(2)
            
            lbl_title = QLabel(title.upper(), self)
            lbl_val = QLabel(value, self)
            
            box.addWidget(lbl_title)
            box.addWidget(lbl_val)
            layout.addLayout(box)
            
            return lbl_title, lbl_val

        # 1. Hostname
        self._t_host, self._v_host = create_block("Hostname", profile.hostname)
        
        # Separator
        sep1 = QFrame(self)
        sep1.setFixedWidth(1)
        layout.addWidget(sep1)

        # 2. Operating System
        self._t_os, self._v_os = create_block("Operating System", f"{profile.os_name} {profile.os_release}")
        
        # Separator
        sep2 = QFrame(self)
        sep2.setFixedWidth(1)
        layout.addWidget(sep2)

        # 3. Uptime
        self._t_up, self._v_up = create_block("System Uptime", f"{profile.uptime_hours:.1f} Hours")
        
        layout.addStretch()

        # 4. Status Indicator (Right side)
        self._status_lbl = QLabel("● SYSTEM ONLINE", self)
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._status_lbl)

        # Store separators for theme updates
        self._separators = [sep1, sep2]

        self.refresh_theme()

    def refresh_theme(self):
        theme = current_theme()
        
        # Banner background
        self.setStyleSheet(f"""
            SystemBanner {{
                background-color: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 12px;
            }}
        """)
        # Style titles
        for t in [self._t_host, self._t_os, self._t_up]:
            t.setStyleSheet(
                f"color: {theme.highlight};"  # <--- Changed from theme.border
                f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
                "font-weight: 700;"
                "letter-spacing: 1px;"
                "border: none;"
            )

        # Style values
        for v in [self._v_host, self._v_os, self._v_up]:
            v.setStyleSheet(
                f"color: {theme.text};"
                f"font-family: {ThemeFonts.FAMILY_MONO};"
                f"font-size: {ThemeFonts.SIZE_BODY}px;"
                "font-weight: 700;"
                "border: none;"
            )

        # Style separators
        for s in self._separators:
            s.setStyleSheet(f"background-color: {theme.border}; border: none;")

        # Style status indicator
        self._status_lbl.setStyleSheet(
            f"color: {theme.highlight};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 800;"
            "letter-spacing: 1px;"
            "border: none;"
        )