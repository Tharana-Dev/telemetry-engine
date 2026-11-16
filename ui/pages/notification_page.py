from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton
)

from ui.models.notification import Notification, AlertId
from ui.widgets.notification_card import NotificationCard
from ui.personalization import current_theme
from ui.theme import ThemeFonts


class NotificationPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._cards: dict[AlertId, NotificationCard] = {}
        self._all_notifs: list[Notification] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(16)

        # --- Header ---
        header_row = QHBoxLayout()
        
        self._title = QLabel("NOTIFICATIONS", self)
        header_row.addWidget(self._title)
        
        header_row.addStretch()
        
        self._clear_btn = QPushButton("Clear Resolved", self)
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self._on_clear_resolved)
        header_row.addWidget(self._clear_btn)
        
        main_layout.addLayout(header_row)

        # --- Scroll Area for feed ---
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._feed_widget = QWidget()
        self._feed_layout = QVBoxLayout(self._feed_widget)
        self._feed_layout.setContentsMargins(0, 0, 0, 0)
        self._feed_layout.setSpacing(10)
        self._feed_layout.addStretch()

        self._scroll.setWidget(self._feed_widget)
        main_layout.addWidget(self._scroll, stretch=1)

        # --- Empty State ---
        self._empty_state = QLabel("All clear. No notifications.", self)
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self._empty_state)

        self.refresh_theme()

    # ------------------------------------------------------------------ API

    def add_notification(self, notif: Notification):
        """Called when worker emits notification_added."""
        self._all_notifs.append(notif)

        card = NotificationCard(notif, self._feed_widget)
        self._cards[notif.id] = card

        # Insert at top: index 0 (before the stretch at the end)
        self._feed_layout.insertWidget(0, card)

        self._empty_state.setVisible(False)

    def mark_resolved(self, alert_id: AlertId):
        """Called when worker emits notification_cleared."""
        card = self._cards.get(alert_id)
        if card:
            card.mark_resolved()

    def _on_clear_resolved(self):
        """Remove all resolved cards from the feed."""
        to_remove = []
        for alert_id, card in self._cards.items():
            if card._resolved:
                to_remove.append((alert_id, card))
        
        for alert_id, card in to_remove:
            self._feed_layout.removeWidget(card)
            card.deleteLater()
            del self._cards[alert_id]
            self._all_notifs = [n for n in self._all_notifs if n.id != alert_id]
        
        if not self._cards:
            self._empty_state.setVisible(True)

    # ------------------------------------------------------------------ Theme

    def refresh_theme(self):
        theme = current_theme()
        
        self._title.setStyleSheet(
            f"color: {theme.highlight};"
            f"font-size: 24px;"
            "font-weight: 900;"
            "letter-spacing: 2px;"
            "border: none;"
        )
        
        self._clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.text};
                border: 1px solid {theme.border};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border: 1px solid {theme.highlight};
                color: {theme.highlight};
            }}
        """)
        
        self._empty_state.setStyleSheet(
            f"color: {theme.text};"
            "font-size: 14px;"
            "border: none;"
        )
        
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {theme.bg};
                width: 10px;
                border: none;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.border};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.highlight};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # Refresh all cards
        for card in self._cards.values():
            card.refresh_theme()