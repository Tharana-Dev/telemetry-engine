from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from personalization import (
    ACCENT_PALETTES,
    AccentPalette,
    current_accent,
    greeting_for_now,
    personalization,
)
from system_probe import DeviceType, SystemProfile
from theme import StyleSheets, ThemeColors, ThemeFonts


class _SectorButton(QPushButton):
    """Clickable quick-jump tile for a single telemetry sector."""

    sector_clicked = Signal(str)

    def __init__(
        self,
        sector_id: str,
        title: str,
        subtitle: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sector_id = sector_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self._title_lbl = QLabel(title, self)
        self._title_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 700;"
            "background: transparent;"
        )

        self._tag_lbl = QLabel("", self)
        self._tag_lbl.setVisible(False)

        top_row.addWidget(self._title_lbl)
        top_row.addStretch()
        top_row.addWidget(self._tag_lbl)

        self._sub_lbl = QLabel(subtitle, self)
        self._sub_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "background: transparent;"
        )

        layout.addLayout(top_row)
        layout.addWidget(self._sub_lbl)

        self.refresh_accent()
        self.clicked.connect(lambda: self.sector_clicked.emit(self.sector_id))

    def refresh_accent(self) -> None:
        """Re-tints hover borders with the currently chosen accent."""
        accent = current_accent()
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {ThemeColors.BG_SURFACE_HOVER};
                border: 1px solid {accent.primary};
            }}
            """
        )

    def set_tag(self, text: str, text_color: str) -> None:
        """Shows a small status tag (e.g., 'Admin Only' or 'Unlocked') on the tile."""
        self._tag_lbl.setText(text)
        self._tag_lbl.setStyleSheet(
            StyleSheets.badge_style(ThemeColors.BG_BASE, text_color)
        )
        self._tag_lbl.setVisible(bool(text))


class _AccentSwatch(QPushButton):
    """A little colored circle in the accent picker row."""

    def __init__(self, palette: AccentPalette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._palette = palette
        self._selected = False
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Use {palette.name} accent")
        self.refresh()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.refresh()

    def refresh(self) -> None:
        ring = ThemeColors.TEXT_PRIMARY if self._selected else self._palette.hover
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {self._palette.primary};
                border: {width}px solid {ring};
                border-radius: 13px;  /* Half of 26 */
            }}
            QPushButton:hover {{
                border: 2px solid {ThemeColors.TEXT_PRIMARY};
            }}
            """
        )


class LaunchpadPanel(QWidget):
    """Right-hand launchpad showing WinTmp admin status and quick-jump sector tiles."""

    start_requested = Signal(str, bool)  # (target_sector_id, skip_next_time)
    restart_admin_requested = Signal()

    def __init__(
        self, profile: SystemProfile | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._sector_buttons: dict[str, _SectorButton] = {}
        self._accent_swatches: list[_AccentSwatch] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        self._init_header(layout)
        self._init_admin_card(layout)
        self._init_sector_grid(layout)
        layout.addStretch()
        self._init_action_bar(layout)

        # Seed swatch selection state to match whatever is already active.
        self._sync_swatch_selection()

        if profile is not None:
            self.update_profile(profile)

    # ------------------------------------------------------------------ header

    def _init_header(self, parent_layout: QVBoxLayout) -> None:
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        # Left: personalized greeting + subtitle
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
        top_row.addLayout(text_col, 1)

        # Right: accent palette picker
        accent_col = QVBoxLayout()
        accent_col.setSpacing(6)

        accent_lbl = QLabel("YOUR ACCENT", self)
        accent_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        accent_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 700;"
            "letter-spacing: 1px;"
        )

        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(6)
        swatch_row.setContentsMargins(0, 0, 0, 0)
        for idx, palette in enumerate(ACCENT_PALETTES):
            swatch = _AccentSwatch(palette, self)
            swatch.clicked.connect(
                lambda checked=False, i=idx: self._on_accent_picked(i)
            )
            swatch_row.addWidget(swatch)
            self._accent_swatches.append(swatch)

        accent_col.addWidget(accent_lbl)
        accent_col.addLayout(swatch_row)
        top_row.addLayout(accent_col)

        parent_layout.addLayout(top_row)

    def _on_accent_picked(self, index: int) -> None:
        personalization().set_accent_index(index)

    def _sync_swatch_selection(self) -> None:
        active = personalization().accent_index
        for i, swatch in enumerate(self._accent_swatches):
            swatch.set_selected(i == active)

    # ------------------------------------------------------------------ admin card

    def _init_admin_card(self, parent_layout: QVBoxLayout) -> None:
        """Prominent WinTmp Administrator status card without cascading child borders."""
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

    # ------------------------------------------------------------------ sector grid

    def _init_sector_grid(self, parent_layout: QVBoxLayout) -> None:
        section_lbl = QLabel("QUICK JUMP TO SECTOR", self)
        section_lbl.setStyleSheet(
            f"color: {ThemeColors.TEXT_MUTED};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            "font-weight: 700;"
            "letter-spacing: 1px;"
        )
        parent_layout.addWidget(section_lbl)

        grid = QGridLayout()
        grid.setSpacing(10)

        sectors = [
            ("cpu", "CPU", "Usage & live MHz speed"),
            ("memory", "Memory", "Used & available RAM"),
            ("gpu", "GPU", "Load, temp, power & fan"),
            ("thermals", "Thermals & Fans", "WinTmp temps & RPMs"),
            ("disk", "Disk I/O & Space", "Read/write & capacity"),
            ("network", "Network", "Up/down speed & drops"),
            ("battery", "Battery & Power", "Charge, watts & health"),
        ]

        for idx, (sec_id, title, subtitle) in enumerate(sectors):
            btn = _SectorButton(sec_id, title, subtitle, self)
            btn.sector_clicked.connect(self._on_sector_clicked)
            self._sector_buttons[sec_id] = btn
            grid.addWidget(btn, idx // 2, idx % 2)

        parent_layout.addLayout(grid)

    # ------------------------------------------------------------------ action bar

    def _init_action_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(12)

        self._skip_checkbox = QCheckBox("Skip welcome screen on startup", self)

        open_all_btn = QPushButton("Open All Graphs", self)
        open_all_btn.setObjectName("PrimaryButton")
        open_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_all_btn.clicked.connect(lambda: self._on_sector_clicked("all"))

        bar.addWidget(self._skip_checkbox)
        bar.addStretch()
        bar.addWidget(open_all_btn)
        parent_layout.addLayout(bar)

    def _on_sector_clicked(self, sector_id: str) -> None:
        self.start_requested.emit(sector_id, self._skip_checkbox.isChecked())

    # ------------------------------------------------------------------ accent refresh

    def refresh_accent(self) -> None:
        """Called by WelcomeWindow when the user picks a new accent swatch."""
        self._sync_swatch_selection()
        for btn in self._sector_buttons.values():
            btn.refresh_accent()

    # ------------------------------------------------------------------ profile

    def update_profile(self, profile: SystemProfile) -> None:
        """Updates greeting, WinTmp admin banner, and available sector tiles."""
        # 1. Personalized greeting + warmer subtitle
        device_word = profile.device_type.label.split()[0].lower()
        if device_word == "unknown":
            device_word = "system"

        self._greeting_lbl.setText(f"{greeting_for_now()}, {profile.username}")
        self._subtitle_lbl.setText(
            f"Your {device_word} is ready — jump into a live sector "
            f"or open the full monitor."
        )

        # 2. Update prominent WinTmp Admin Card
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

        # 3. Tag the Thermals tile based on Admin rights
        thermals_btn = self._sector_buttons.get("thermals")
        if thermals_btn is not None:
            if profile.is_admin:
                thermals_btn.set_tag("WinTmp Ready", ThemeColors.STATUS_OK)
            else:
                thermals_btn.set_tag("Admin Only", ThemeColors.STATUS_WARN)

        # 4. Show Battery tile only on Laptops
        battery_btn = self._sector_buttons.get("battery")
        if battery_btn is not None:
            battery_btn.setVisible(profile.device_type == DeviceType.LAPTOP)
            