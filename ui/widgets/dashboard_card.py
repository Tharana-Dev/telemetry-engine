from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QProgressBar

from ui.theme import ThemeColors, ThemeFonts
from ui.personalization import current_theme


class DashboardCard(QFrame):
    """A clean, space-filling summary card with hero value + sub-stats."""
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
        main_layout.addWidget(self._hero_label)

        # 3. Progress Bar (Hidden by default)
        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setVisible(False)
        main_layout.addWidget(self._progress_bar)

        main_layout.addSpacing(16)
        main_layout.addStretch(1) 


        # 4. Sub-Stats
        self._rows: dict[str, QLabel] = {}
        for key in rows:
            row_widget = QWidget(self)
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 4)

            k_lbl = QLabel(key.upper(), row_widget)
            v_lbl = QLabel("--", row_widget)
            v_lbl.setWordWrap(True)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row_layout.addWidget(k_lbl)
            row_layout.addStretch()
            row_layout.addWidget(v_lbl)

            main_layout.addWidget(row_widget)
            self._rows[key] = v_lbl
        self.refresh_theme()

    def set_hero(self, value: str, progress_pct: float | None = None, color: str | None = None):
        """Sets the large text and optional progress bar."""
        theme = current_theme()
        self._hero_label.setText(value)
        text_color = color if color else theme.text
        self._hero_label.setStyleSheet(
            f"color: {text_color};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 32px; font-weight: 700; border: none;"
        )

        if progress_pct is not None:
            self._progress_bar.setVisible(True)
            self._progress_bar.setValue(int(progress_pct))
            bar_color = color if color else theme.highlight
            self._progress_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: {theme.bg}; border: none; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 3px; }}
            """)
        else:
            self._progress_bar.setVisible(False)

    def update_row(self, key: str, value: str, color: str | None = None):
        lbl = self._rows.get(key)
        if lbl:
            theme = current_theme()
            lbl.setText(value)
            text_color = color if color else theme.text
            lbl.setStyleSheet(
                f"color: {text_color};"
                f"font-family: {ThemeFonts.FAMILY_MONO};"
                "font-size: 14px; font-weight: 600; border: none;"
            )

    def refresh_theme(self) -> None:
        theme = current_theme()
        self.setStyleSheet(f"""
            DashboardCard {{
                background-color: {theme.surface};
                border: 1px solid {theme.border};
                border-top: 3px solid {theme.highlight};
                border-radius: 12px;
            }}
            DashboardCard:hover {{
                background-color: {theme.border};
                border: 1px solid {theme.highlight};
                border-top: 3px solid {theme.highlight};
            }}
        """)
        self._title_label.setStyleSheet(
            f"color: {theme.highlight};"
            f"font-size: {ThemeFonts.SIZE_TITLE}px;"
            "font-weight: 800;"
            "letter-spacing: 1px;"
            "border: none;"
        )
        self._hero_label.setStyleSheet(
            f"color: {theme.text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 32px; font-weight: 700; border: none;"
        )
        for key, lbl in self._rows.items():
            lbl.setStyleSheet(
                f"color: {theme.text};"
                f"font-family: {ThemeFonts.FAMILY_MONO};"
                "font-size: 14px; font-weight: 600; border: none;"
            )