"""Runtime personalization: theme palettes, greetings, monogram helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from PySide6.QtCore import QObject, Signal

@dataclass(frozen=True)
class ThemePalette:
    name: str
    bg: str          # Primary: The main background
    surface: str     # Slightly lighter/darker for cards
    text: str        # Secondary: Main text color
    highlight: str   # 3rd Color: Accents, borders, graphs, alerts
    border: str      # Subtle borders

# 4 Distinct Theme Packs
# Order: (name, bg, surface [dark cards], text [numbers/labels], highlight [card titles/graphs], border [hover/lines])
THEME_PALETTES: tuple[ThemePalette, ...] = (
    # 1. Arctic Cobalt (Deep Midnight-Ocean BG + Rich Cobalt-Slate Cards + Ice-White Text + Electric Cyan Accents)
    ThemePalette("Arctic Cobalt", "#091526", "#11243E", "#F8FAFC", "#38BDF8", "#1E3A5F"),

    # 2. Cyber Gold (Pitch Black BG + Dark Onyx Cards + Warm Cream Text + Electric Yellow Accents)
    ThemePalette("Cyber Gold", "#050507", "#121216", "#FAF5E4", "#FACC15", "#27272A"),

    # 3. Emerald Pulse (Deep Jungle-Black BG + Dark Emerald Cards + Crisp Mint-White Text + Neon Aqua Accents)
    ThemePalette("Emerald Pulse", "#022C22", "#064E3B", "#ECFDF5", "#2DD4BF", "#047857"),

    # 4. Nebula Frost (Deep Midnight-Violet BG + Royal Indigo Cards + Crisp Ice-White Text + Electric Violet Accents)
    ThemePalette("Nebula Frost", "#0F0C29", "#1E1B4B", "#F8FAFC", "#A78BFA", "#3730A3"),
)


class Personalization(QObject):
    theme_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._theme_index = 0

    @property
    def theme_index(self) -> int:
        return self._theme_index

    @property
    def theme(self) -> ThemePalette:
        return THEME_PALETTES[self._theme_index]

    def set_theme_index(self, index: int) -> None:
        index = max(0, min(index, len(THEME_PALETTES) - 1))
        if index == self._theme_index:
            return
        self._theme_index = index
        self.theme_changed.emit()

_PERSONALIZATION = Personalization()

def personalization() -> Personalization:
    return _PERSONALIZATION

def current_theme() -> ThemePalette:
    return _PERSONALIZATION.theme

def greeting_for_now() -> str:
    hour = datetime.now().hour
    if 5 <= hour < 12: return "Good morning"
    if 12 <= hour < 17: return "Good afternoon"
    if 17 <= hour < 22: return "Good evening"
    return "Working late"

def monogram_for(text: str) -> str:
    for ch in (text or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "★"