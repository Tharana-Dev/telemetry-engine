from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QProgressBar

from ui.theme import ThemeColors, ThemeFonts
from ui.personalization import current_accent


class DashboardCard(QFrame):
    """A clean, space-filling summary card."""
    def __init__(self, title: str, rows: list[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(12)

        # 1. Title
        self._title_label = QLabel(title.upper(), self)
        main_layout.addWidget(self._title_label)

        # 2. Hero Value
        self._hero_label = QLabel("--", self)
        self._hero_label.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: 32px; font-weight: 700; border: none;")
        main_layout.addWidget(self._hero_label)

        # 3. Progress Bar (Hidden by default)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)
        
        main_layout.addSpacing(16)

        # 4. Sub-Stats (Clean key-value rows)
        self._rows: dict[str, QLabel] = {}
        for key in rows:
            row_widget = QWidget(self)
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 4)
            
            k_lbl = QLabel(key.upper(), row_widget)
            k_lbl.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 12px; font-weight: 700; border: none;")
            
            v_lbl = QLabel("--", row_widget)
            v_lbl.setWordWrap(True)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v_lbl.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: 14px; font-weight: 600; border: none;")
            
            row_layout.addWidget(k_lbl)
            row_layout.addStretch()
            row_layout.addWidget(v_lbl)
            
            main_layout.addWidget(row_widget)
            self._rows[key] = v_lbl

        main_layout.addStretch()
        self.refresh_accent()

    def set_hero(self, value: str, progress_pct: float | None = None, color: str | None = None):
        """Sets the large text and optional progress bar."""
        self._hero_label.setText(value)
        text_color = color if color else ThemeColors.TEXT_PRIMARY
        self._hero_label.setStyleSheet(f"color: {text_color}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: 32px; font-weight: 700; border: none;")

        if progress_pct is not None:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(int(progress_pct))
            bar_color = color if color else current_accent().primary
            self._progress_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: {ThemeColors.BG_BASE}; border: none; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 3px; }}
            """)
        else:
            self._progress_bar.setVisible(False)

    def update_row(self, key: str, value: str, color: str | None = None):
        lbl = self._rows.get(key)
        if lbl:
            lbl.setText(value)
            text_color = color if color else ThemeColors.TEXT_PRIMARY
            lbl.setStyleSheet(f"color: {text_color}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: 14px; font-weight: 600; border: none;")

    def refresh_accent(self):
        accent = current_accent()
        self.setStyleSheet(f"""
            DashboardCard {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 16px;
            }}
            DashboardCard:hover {{
                border: 1px solid {accent.primary};
                background-color: {ThemeColors.BG_SURFACE_HOVER};
            }}
        """)
        self._title_label.setStyleSheet(f"color: {accent.primary}; font-size: 16px; font-weight: 800; letter-spacing: 2px; border: none;")