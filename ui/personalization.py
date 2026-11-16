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
    # 1. Aero Interceptor (Deep Sky-Navy BG + Rich Cobalt Cards + Ice-White Text + Electric Sky Accents)
    ThemePalette("Aero Interceptor", "#082F49", "#0C4A6E", "#F0F9FF", "#38BDF8", "#0369A1"),

    # 2. Night City (Carbon Black BG + Dark Graphite Cards + Luminous Yellow Text + Neon Crimson Accents)
    ThemePalette("Night City", "#09090B", "#18181B", "#FDE047", "#FF2E63", "#27272A"),

    # 3. Emerald Pulse (Deep Jungle-Black BG + Dark Emerald Cards + Crisp Mint-White Text + Neon Aqua Accents)
    ThemePalette("Emerald Pulse", "#022C22", "#064E3B", "#ECFDF5", "#2DD4BF", "#047857"),

    # 4. Crimson Stealth (Obsidian BG + Deep Maroon-Slate Cards + Pure Crisp White Text + Racing Red Accents)
    ThemePalette("Crimson Stealth", "#0F0A0C", "#1F1318", "#F8FAFC", "#F43F5E", "#381E28"),
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