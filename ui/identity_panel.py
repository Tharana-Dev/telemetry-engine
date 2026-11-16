from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.personalization import current_theme, monogram_for
from ui.system_probe import DeviceType, SystemProfile
from ui.theme import StyleSheets, ThemeFonts

_LAPTOP_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="__ACCENT__" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="4" width="18" height="12" rx="2" ry="2" />
  <line x1="2" y1="20" x2="22" y2="20" />
  <line x1="8" y1="16" x2="7" y2="20" />
  <line x1="16" y1="16" x2="17" y2="20" />
</svg>
""".strip()

_DESKTOP_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="__ACCENT__" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round">
  <rect x="2" y="4" width="13" height="10" rx="1.5" />
  <line x1="8.5" y1="14" x2="8.5" y2="18" />
  <line x1="5.5" y1="18" x2="11.5" y2="18" />
  <rect x="17" y="3" width="5" height="16" rx="1" />
  <circle cx="19.5" cy="6.5" r="0.7" fill="__ACCENT__" />
  <line x1="18.5" y1="15.5" x2="20.5" y2="15.5" />
</svg>
""".strip()

_UNKNOWN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
     stroke="__ACCENT__" stroke-width="1.8"
     stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="4" width="18" height="6" rx="1.5" />
  <rect x="3" y="14" width="18" height="6" rx="1.5" />
  <circle cx="7" cy="7" r="0.8" fill="__ACCENT__" />
  <circle cx="7" cy="17" r="0.8" fill="__ACCENT__" />
  <line x1="11" y1="7" x2="17" y2="7" />
  <line x1="11" y1="17" x2="17" y2="17" />
</svg>
""".strip()


def _svg_for(device_type: DeviceType, accent_hex: str) -> str:
    """Returns the matching device SVG, retinted with the live accent color."""
    template = {
        DeviceType.LAPTOP: _LAPTOP_SVG,
        DeviceType.DESKTOP: _DESKTOP_SVG,
        DeviceType.UNKNOWN: _UNKNOWN_SVG,
    }.get(device_type, _UNKNOWN_SVG)
    return template.replace("__ACCENT__", accent_hex)


class _ElidedValueLabel(QLabel):
    """Right-aligned monospace label that elides overflow text cleanly."""

    def __init__(self, text: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._full_text = text
        self.setToolTip(text)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"color: {current_theme().text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 600;"
        )

    def set_value(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width()
        )
        super().setText(elided)


class _SpecRow(QWidget):
    """Key-value row for hardware specs with dynamic value updates."""

    def __init__(
        self, label: str, value: str = "—", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self.key_lbl = QLabel(label.upper(), self)
        self._val_lbl = _ElidedValueLabel(value, self)

        layout.addWidget(self.key_lbl)
        layout.addWidget(self._val_lbl, 1)
        
        self.refresh_theme()

    def refresh_theme(self):
        self.key_lbl.setStyleSheet(
            f"color: {current_theme().text};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 600;"
        )
        self._val_lbl.setStyleSheet(
            f"color: {current_theme().text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 600;"
        )

    def set_value(self, text: str) -> None:
        self._val_lbl.set_value(text)


class IdentityPanel(QFrame):
    """Left telemetry card displaying device identity, hardware specs, and power context."""

    def __init__(
        self, profile: SystemProfile | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IdentityPanel")
        self._profile: SystemProfile | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self._init_header(layout)
        self._divider1 = self._make_divider()
        layout.addWidget(self._divider1)
        self._init_specs(layout)
        self._divider2 = self._make_divider()
        layout.addWidget(self._divider2)
        self._init_power_box(layout)
        layout.addStretch()
        self._init_footer(layout)

        self.refresh_theme()

        if profile is not None:
            self.update_profile(profile)

    # ------------------------------------------------------------------ header

    def _init_header(self, parent_layout: QVBoxLayout) -> None:
        self.section_lbl = QLabel("YOUR SYSTEM", self)
        parent_layout.addWidget(self.section_lbl)

        # Personal monogram avatar
        self._monogram = QLabel("★", self)
        self._monogram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._monogram.setFixedSize(72, 72)
        parent_layout.addWidget(self._monogram)

        self._title_lbl = QLabel("Detecting System...", self)
        parent_layout.addWidget(self._title_lbl)

        os_row = QHBoxLayout()
        os_row.setContentsMargins(0, 0, 0, 0)
        os_row.setSpacing(8)

        self._os_badge = QLabel("—", self)

        # Small device glyph next to the OS pill
        self._device_icon = QSvgWidget(self)
        self._device_icon.setFixedSize(24, 24)
        self._device_icon.setStyleSheet("background-color: transparent; border: none;")

        os_row.addWidget(self._os_badge)
        os_row.addWidget(self._device_icon)
        os_row.addStretch()
        parent_layout.addLayout(os_row)

    # ------------------------------------------------------------------ footer

    def _init_footer(self, parent_layout: QVBoxLayout) -> None:
        self._personal_footer = QLabel("—", self)
        parent_layout.addWidget(self._personal_footer)

    def _refresh_monogram(self) -> None:
        theme = current_theme()
        self._monogram.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.bg};
                color: {theme.highlight};
                border: 2px solid {theme.highlight};
                border-radius: 36px;
                font-family: {ThemeFonts.FAMILY_UI};
                font-size: 28px;
                font-weight: 800;
            }}
        """)

    # ------------------------------------------------------------------ specs

    def _init_specs(self, parent_layout: QVBoxLayout) -> None:
        self._row_hostname = _SpecRow("Hostname", parent=self)
        self._row_cpu = _SpecRow("Processor", parent=self)
        self._row_ram = _SpecRow("Memory", parent=self)
        self._row_uptime = _SpecRow("Uptime", parent=self)

        specs_layout = QVBoxLayout()
        specs_layout.setSpacing(6)
        specs_layout.addWidget(self._row_hostname)
        specs_layout.addWidget(self._row_cpu)
        specs_layout.addWidget(self._row_ram)
        specs_layout.addWidget(self._row_uptime)
        parent_layout.addLayout(specs_layout)

    # ------------------------------------------------------------------ power

    def _init_power_box(self, parent_layout: QVBoxLayout) -> None:
        self.power_box = QFrame(self)
        box_layout = QVBoxLayout(self.power_box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)

        box_layout.addWidget(self._build_laptop_power_view(self.power_box))
        box_layout.addWidget(self._build_desktop_power_view(self.power_box))
        parent_layout.addWidget(self.power_box)

    def _build_laptop_power_view(self, parent: QWidget) -> QWidget:
        self._laptop_power_widget = QWidget(parent)
        self._laptop_power_widget.setStyleSheet(
            "background-color: transparent; border: none;"
        )

        layout = QVBoxLayout(self._laptop_power_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self._src_badge = QLabel(self._laptop_power_widget)
        self._pct_lbl = QLabel(self._laptop_power_widget)

        top_row.addWidget(self._src_badge)
        top_row.addStretch()
        top_row.addWidget(self._pct_lbl)
        layout.addLayout(top_row)

        self._battery_bar = QProgressBar(self._laptop_power_widget)
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setTextVisible(False)
        self._battery_bar.setFixedHeight(8)
        layout.addWidget(self._battery_bar)

        return self._laptop_power_widget

    def _build_desktop_power_view(self, parent: QWidget) -> QWidget:
        self._desktop_power_widget = QWidget(parent)
        self._desktop_power_widget.setStyleSheet(
            "background-color: transparent; border: none;"
        )

        row = QHBoxLayout(self._desktop_power_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._desktop_dot = QLabel("●", self._desktop_power_widget)
        self._desktop_status_lbl = QLabel("Mains AC • Continuous Power", self._desktop_power_widget)

        row.addWidget(self._desktop_dot)
        row.addWidget(self._desktop_status_lbl)
        row.addStretch()
        return self._desktop_power_widget

    def _make_divider(self) -> QFrame:
        line = QFrame(self)
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    # ------------------------------------------------------------------ accent refresh

    def refresh_theme(self) -> None:
        """Re-render the parts of this panel tinted by the current theme."""
        theme = current_theme()
        
        # 1. Panel Background
        self.setStyleSheet(f"""
            QFrame#IdentityPanel {{
                background-color: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 12px;
            }}
        """)
        
        # 2. Static Labels
        self.section_lbl.setStyleSheet(f"color: {theme.border}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 700; letter-spacing: 1px;")
        self._title_lbl.setStyleSheet(f"color: {theme.text}; font-size: {ThemeFonts.SIZE_TITLE}px; font-weight: 700;")
        self._personal_footer.setStyleSheet(f"color: {theme.border}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 500; letter-spacing: 0.3px;")
        
        # 3. Dividers
        divider_style = f"background-color: {theme.border}; border: none;"
        self._divider1.setStyleSheet(divider_style)
        self._divider2.setStyleSheet(divider_style)
        
        # 4. Power Box
        self.power_box.setStyleSheet(f"background-color: {theme.bg}; border: 1px solid {theme.border}; border-radius: 8px;")
        self._pct_lbl.setStyleSheet(f"color: {theme.text}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 700; border: none;")
        self._desktop_dot.setStyleSheet(f"color: {theme.highlight}; font-size: {ThemeFonts.SIZE_CAPTION}px; border: none;")
        self._desktop_status_lbl.setStyleSheet(f"color: {theme.text}; font-size: {ThemeFonts.SIZE_CAPTION}px; font-weight: 600; border: none;")

        # 5. Spec Rows
        for row in [self._row_hostname, self._row_cpu, self._row_ram, self._row_uptime]:
            row.refresh_theme()
        
        # 6. Monogram & Icon
        self._refresh_monogram()
        
        if self._profile is not None:
            self.update_profile(self._profile)

    # ------------------------------------------------------------------ update

    def update_profile(self, profile: SystemProfile) -> None:
        """Populates or refreshes all labels, the SVG icon, and the power section."""
        self._profile = profile
        theme = current_theme()

        # Retinted device glyph next to the OS pill.
        raw_svg = _svg_for(profile.device_type, theme.highlight)
        self._device_icon.load(QByteArray(raw_svg.encode("utf-8")))

        # Personal touches.
        self._monogram.setText(monogram_for(profile.username))
        self._personal_footer.setText(f"Signed in as {profile.username}")
        
        self._title_lbl.setText(profile.device_type.label)
        self._os_badge.setText(f"{profile.os_name} {profile.os_release}")
        self._os_badge.setStyleSheet(
            StyleSheets.badge_style(theme.bg, theme.highlight)
        )

        self._row_hostname.set_value(profile.hostname)
        self._row_cpu.set_value(profile.cpu_summary)
        self._row_ram.set_value(f"{profile.ram_total_gb} GB RAM")
        self._row_uptime.set_value(f"{profile.uptime_hours} hrs")

        is_laptop_battery = (
            profile.device_type == DeviceType.LAPTOP
            and profile.battery_percent is not None
        )
        self._laptop_power_widget.setVisible(is_laptop_battery)
        self._desktop_power_widget.setVisible(not is_laptop_battery)

        if is_laptop_battery:
            is_ac = profile.power_source == "AC Power"
            badge_color = theme.highlight if is_ac else "#F59E0B" # Highlight or Amber

            self._src_badge.setText(profile.power_source)
            self._src_badge.setStyleSheet(
                StyleSheets.badge_style(theme.surface, badge_color)
            )
            self._pct_lbl.setText(f"{profile.battery_percent}%")
            self._battery_bar.setValue(profile.battery_percent)
            self._battery_bar.setStyleSheet(
                f"""
                QProgressBar {{
                    background-color: {theme.surface};
                    border: none;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {badge_color};
                    border-radius: 4px;
                }}
                """
            )