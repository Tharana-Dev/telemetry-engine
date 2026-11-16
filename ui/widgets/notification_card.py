from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel

from ui.models.notification import Notification, AlertSeverity
from ui.personalization import current_theme
from ui.theme import ThemeFonts


class NotificationCard(QFrame):
    """A single alert entry in the notification feed."""
    
    def __init__(self, notif: Notification, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._notif = notif
        self._resolved = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # --- Top row: [SOURCE] tag + severity badge + timestamp ---
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self._source_lbl = QLabel(f"[{notif.source.value}]", self)
        self._severity_lbl = QLabel(notif.severity.value, self)
        self._time_lbl = QLabel(notif.timestamp.strftime("%H:%M:%S"), self)
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        top_row.addWidget(self._source_lbl)
        top_row.addWidget(self._severity_lbl)
        top_row.addStretch()
        top_row.addWidget(self._time_lbl)
        layout.addLayout(top_row)

        # --- Message ---
        self._message_lbl = QLabel(notif.message, self)
        self._message_lbl.setWordWrap(True)
        layout.addWidget(self._message_lbl)

        # --- Resolved tag (hidden until cleared) ---
        self._resolved_lbl = QLabel("✓ RESOLVED", self)
        self._resolved_lbl.setVisible(False)
        layout.addWidget(self._resolved_lbl)

        self.refresh_theme()

    def mark_resolved(self):
        """Called when the worker fires notification_cleared."""
        self._resolved = True
        self._resolved_lbl.setVisible(True)
        self.refresh_theme()

    def refresh_theme(self):
        theme = current_theme()
        
        # Severity color: highlight for warning, red for critical, muted for info
        if self._notif.severity == AlertSeverity.CRITICAL:
            accent_color = "#EF4444"
        elif self._notif.severity == AlertSeverity.WARNING:
            accent_color = theme.highlight
        else:
            accent_color = theme.text

        # Resolved cards fade to a muted background
        bg_color = theme.border if self._resolved else theme.surface
        left_border = theme.text if self._resolved else accent_color

        self.setStyleSheet(f"""
            NotificationCard {{
                background-color: {bg_color};
                border: 1px solid {theme.border};
                border-left: 4px solid {left_border};
                border-radius: 8px;
            }}
            NotificationCard:hover {{
                background-color: {theme.border};
            }}
        """)

        # Source tag
        self._source_lbl.setStyleSheet(
            f"color: {theme.text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 13px;"
            "font-weight: 800;"
            "letter-spacing: 1px;"
            "border: none;"
        )

        # Severity badge
        self._severity_lbl.setStyleSheet(
            f"color: {accent_color};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 11px;"
            "font-weight: 700;"
            "border: none;"
        )

        # Timestamp
        self._time_lbl.setStyleSheet(
            f"color: {theme.text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 11px;"
            "border: none;"
        )

        # Message
        self._message_lbl.setStyleSheet(
            f"color: {theme.text};"
            "font-size: 13px;"
            "border: none;"
        )

        # Resolved label
        self._resolved_lbl.setStyleSheet(
            f"color: {theme.text};"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            "font-size: 11px;"
            "font-weight: 700;"
            "letter-spacing: 1px;"
            "border: none;"
        )