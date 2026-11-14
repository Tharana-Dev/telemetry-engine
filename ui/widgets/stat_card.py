from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QHBoxLayout, QWidget, QSizePolicy

from ui.theme import ThemeColors, ThemeFonts
from ui.personalization import current_accent


class StatRow(QWidget):
    def __init__(self, key: str, value: str = "--", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6) # Slightly more vertical padding
        layout.setSpacing(8)

        self.key_label = QLabel(key, self)
        self.key_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_SECONDARY};"
            f"font-size: 18px;"  # <--- INCREASED
            "font-weight: 600;"
            "border: none;"
        )

        self.value_label = QLabel(value, self)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.value_label.setStyleSheet(
            f"color: {ThemeColors.TEXT_PRIMARY};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: 18px;"  # <--- INCREASED
            "font-weight: 700;"
            "border: none;"
        )

        layout.addWidget(self.key_label)
        layout.addStretch()
        layout.addWidget(self.value_label)

    def set_value(self, value_str: str, color: str | None = None) -> None:
        self.value_label.setText(value_str)
        if color:
            self.value_label.setStyleSheet(
                f"color: {color};"
                f"font-family: {ThemeFonts.FAMILY_MONO};"
                f"font-size: 20px;"  # <--- INCREASED
                "font-weight: 700;"
                "border: none;"
            )
        else:
            self.value_label.setStyleSheet(
                f"color: {ThemeColors.TEXT_PRIMARY};"
                f"font-family: {ThemeFonts.FAMILY_MONO};"
                f"font-size: 20px;"  # <--- INCREASED
                "font-weight: 700;"
                "border: none;"
            )


class StatCard(QFrame):
    def __init__(self, title: str, rows: list[str], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Give cards a nice minimum height so they don't squish
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._title = title
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(12)

        # Card Title
        self._title_label = QLabel(self._title.upper(), self)
        self._title_label.setStyleSheet(
            f"color: {current_accent().primary};"
            f"font-size: 24px;"  # <--- INCREASED
            "font-weight: 800;"
            "letter-spacing: 1px;"
            "border: none;"
        )
        main_layout.addWidget(self._title_label)
        
        main_layout.addSpacing(8)

        self._rows: dict[str, StatRow] = {}
        for key in rows:
            row = StatRow(key, parent=self)
            main_layout.addWidget(row)
            self._rows[key] = row

        # Push all text to the top of the card, leaving empty space at the bottom if it grows
        main_layout.addStretch()

        # Apply dynamic card styling
        self.refresh_accent()

    def update_row(self, key: str, value: str, color: str | None = None):
        row = self._rows.get(key, None)
        if row is not None:
            row.set_value(value, color)

    def set_row_visible(self, key: str, visible: bool):
        row = self._rows.get(key, None)
        if row is not None:
            row.setVisible(visible)

    def refresh_accent(self):
        accent = current_accent()
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ThemeColors.BG_SURFACE};
                border: 1px solid {ThemeColors.BORDER_SUBTLE};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border: 1px solid {accent.primary};
            }}
        """)
        if hasattr(self, "_title_label"):
            self._title_label.setStyleSheet(
                f"color: {accent.primary};"
                f"font-size: 24px;"
                "font-weight: 800;"
                "letter-spacing: 1px;"
                "border: none;"
            )