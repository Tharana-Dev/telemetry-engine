"""Runtime personalization: user-chosen accent palette, friendly greetings, monogram helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class AccentPalette:
    name: str
    primary: str
    hover: str
    pressed: str


ACCENT_PALETTES: tuple[AccentPalette, ...] = (
    AccentPalette("Sky",     "#38BDF8", "#0284C7", "#0369A1"),
    AccentPalette("Violet",  "#A78BFA", "#8B5CF6", "#7C3AED"),
    AccentPalette("Emerald", "#34D399", "#10B981", "#059669"),
    AccentPalette("Ember",   "#FB923C", "#F97316", "#EA580C"),
    AccentPalette("Rose",    "#F472B6", "#EC4899", "#DB2777"),
)


class Personalization(QObject):
    """Tracks the user's chosen accent palette and notifies listeners on change."""

    accent_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._accent_index = 0

    @property
    def accent_index(self) -> int:
        return self._accent_index

    @property
    def accent(self) -> AccentPalette:
        return ACCENT_PALETTES[self._accent_index]

    def set_accent_index(self, index: int) -> None:
        index = max(0, min(index, len(ACCENT_PALETTES) - 1))
        if index == self._accent_index:
            return
        self._accent_index = index
        self.accent_changed.emit()


_PERSONALIZATION = Personalization()


def personalization() -> Personalization:
    return _PERSONALIZATION


def current_accent() -> AccentPalette:
    return _PERSONALIZATION.accent


def greeting_for_now() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "Good morning"
    if 12 <= hour < 17:
        return "Good afternoon"
    if 17 <= hour < 22:
        return "Good evening"
    return "Working late"


def monogram_for(text: str) -> str:
    """First alphanumeric character of the hostname, uppercased. Falls back to ★."""
    for ch in (text or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "★"