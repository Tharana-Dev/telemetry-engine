from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QProgressBar, QGridLayout

from ui.theme import ThemeColors, ThemeFonts
from ui.personalization import current_accent


class DashboardCard(QFrame):
    """A premium, space-filling summary card with a Hero value and progress bar."""
    def __init__(self, title: str, hero_unit: str, rows: list[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 1. Title
        self._title_label = QLabel(title.upper(), self)
        main_layout.addWidget(self._title_label)

        # 2. Hero Value & Progress Bar
        hero_layout = QVBoxLayout()
        hero_layout.setSpacing(8)
        
        self._hero_label = QLabel(f"-- {hero_unit}", self)
        hero_layout.addWidget(self._hero_label)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(10)
        hero_layout.addWidget(self._progress_bar)
        
        main_layout.addLayout(hero_layout)
        
        main_layout.addSpacing(10)

        # 3. Sub-Stats Grid
        self._sub_grid = QGridLayout()
        self._sub_grid.setSpacing(12)
        self._rows: dict[str, QLabel] = {}

        for index, key in enumerate(rows):
            row_idx = index // 2
            col_idx = index % 2
            
            container = QWidget(self)
            vbox = QVBoxLayout(container)
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(2)

            k_lbl = QLabel(key.upper(), container)
            k_lbl.setStyleSheet(f"color: {ThemeColors.TEXT_MUTED}; font-size: 11px; font-weight: 700; border: none;")
            
            v_lbl = QLabel("--", container)
            v_lbl.setWordWrap(True)
            v_lbl.setStyleSheet(f"color: {ThemeColors.TEXT_PRIMARY}; font-family: {ThemeFonts.FAMILY_MONO}; font-size: 14px; font-weight: 600; border: none;")
            
            vbox.addWidget(k_lbl)
            vbox.addWidget(v_lbl)
            
            self._sub_grid.addWidget(container, row_idx, col_idx)
            self._rows[key] = v_lbl

        main_layout.addLayout(self._sub_grid)
        main_layout.addStretch()
        
        self.refresh_accent()

    def set_hero(self, value: str, progress_pct: float | None = None, color: str | None = None):
        """Sets the giant text and updates the progress bar."""
        self._hero_label.setText(value)
        
        text_color = color if color else ThemeColors.TEXT_PRIMARY
        self._hero_label.setStyleSheet(f"""
            color: {text_color};
            font-family: {ThemeFonts.FAMILY_MONO};
            font-size: 48px;
            font-weight: 900;
            border: none;
        """)

        if progress_pct is not None:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(int(progress_pct))
            bar_color = color if color else current_accent().primary
            self._progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {ThemeColors.BG_BASE};
                    border: none;
                    border-radius: 5px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 5px;
                }}
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
        self._title_label.setStyleSheet(
            f"color: {accent.primary};"
            f"font-size: 16px;"
            "font-weight: 800;"
            "letter-spacing: 2px;"
            "border: none;"
        )