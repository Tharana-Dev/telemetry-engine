from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy

from ui.personalization import current_theme
from ui.theme import ThemeFonts


class StatRow(QWidget):
    def __init__(self, key: str, value: str = "--", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)

        self.key_label = QLabel(key, self)
        self.key_label.setStyleSheet(
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 600;"
            "border: none;"
        )
        self.key_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.value_label = QLabel(value, self)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setStyleSheet(
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 700;"
            "border: none;"
        )

        layout.addWidget(self.key_label)
        layout.addStretch()
        layout.addWidget(self.value_label)
        
        self.refresh_theme()

    def refresh_theme(self):
        theme = current_theme()
        self.key_label.setStyleSheet(
            f"color: {theme.text};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 600;"
            "border: none;"
        )
        self.value_label.setStyleSheet(
            f"color: {theme.text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 700;"
            "border: none;"
        )

    def set_value(self, value_str: str, color: str | None = None) -> None:
        theme = current_theme()
        self.value_label.setText(value_str)
        text_color = color if color else theme.text
        self.value_label.setStyleSheet(
            f"color: {text_color};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_BODY}px;"
            "font-weight: 700;"
            "border: none;"
        )


class StatCard(QFrame):
    def __init__(self, title: str, rows: list[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._title = title
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(12)

        self._title_label = QLabel(self._title.upper(), self)
        self._title_label.setWordWrap(True)
        main_layout.addWidget(self._title_label)

        self._rows: dict[str, StatRow] = {}
        for key in rows:
            row = StatRow(key, parent=self)
            main_layout.addWidget(row)
            self._rows[key] = row

        self.refresh_theme()

    def update_row(self, key: str, value: str, color: str | None = None):
        row = self._rows.get(key, None)
        if row is not None:
            row.set_value(value, color)

    def set_row_visible(self, key: str, visible: bool):
        row = self._rows.get(key, None)
        if row is not None:
            row.setVisible(visible)

    def refresh_theme(self):
        theme = current_theme()
        self.setStyleSheet(f"""
            StatCard {{
                background-color: {theme.surface};
                border: 1px solid {theme.border};
                border-radius: 12px;
            }}
            StatCard:hover {{
                border: 1px solid {theme.highlight};
            }}
        """)
        self._title_label.setStyleSheet(
            f"color: {theme.highlight};"
            f"font-size: {ThemeFonts.SIZE_TITLE}px;"
            "font-weight: 800;"
            "letter-spacing: 1px;"
            "border: none;"
        )
        for row in self._rows.values():
            row.refresh_theme()