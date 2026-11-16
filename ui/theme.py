from dataclasses import dataclass
from ui.personalization import current_theme


class _ThemeColorsProxy:
    """Proxy that reads colors from the active theme at access time."""
    @property
    def BG_BASE(self) -> str: return current_theme().bg
    @property
    def BG_SURFACE(self) -> str: return current_theme().surface
    @property
    def BG_SURFACE_HOVER(self) -> str: return current_theme().border
    @property
    def BG_CARD_ACTIVE(self) -> str: return current_theme().surface

    @property
    def BORDER_SUBTLE(self) -> str: return current_theme().border
    @property
    def BORDER_ACCENT(self) -> str: return current_theme().highlight

    @property
    def TEXT_PRIMARY(self) -> str: return current_theme().text
    @property
    def TEXT_SECONDARY(self) -> str: return current_theme().text
    @property
    def TEXT_MUTED(self) -> str: return current_theme().border

    @property
    def ACCENT_PRIMARY(self) -> str: return current_theme().highlight
    @property
    def ACCENT_HOVER(self) -> str: return current_theme().highlight
    @property
    def ACCENT_PRESSED(self) -> str: return current_theme().border

    @property
    def STATUS_OK(self) -> str: return current_theme().highlight
    @property
    def STATUS_WARN(self) -> str: return "#F59E0B"
    @property
    def STATUS_ERR(self) -> str: return "#EF4444"


# IMPORTANT: Export an INSTANCE, not the class
ThemeColors = _ThemeColorsProxy()


@dataclass(frozen=True)
class ThemeFonts:
    FAMILY_UI: str = "Segoe UI, Inter, Arial, sans-serif"
    FAMILY_MONO: str = "Consolas, JetBrains Mono, monospace"
    SIZE_HERO: int = 28
    SIZE_TITLE: int = 20
    SIZE_BODY: int = 15
    SIZE_CAPTION: int = 13


class StyleSheets:
    @staticmethod
    def get_main_stylesheet() -> str:
        c = ThemeColors  # Now this is the INSTANCE, so c.BG_BASE is a string
        f = ThemeFonts
        theme = current_theme()

        return f"""
        QMainWindow, QWidget {{
            background-color: {c.BG_BASE};
            color: {c.TEXT_PRIMARY};
            font-family: {f.FAMILY_UI};
            font-size: {f.SIZE_BODY}px;
        }}

        QLabel {{
            background-color: transparent;
            border: none;
        }}

        QFrame#IdentityPanel {{
            background-color: {c.BG_SURFACE};
            border: 1px solid {c.BORDER_SUBTLE};
            border-radius: 12px;
        }}

        QPushButton#PrimaryButton {{
            background-color: {c.ACCENT_PRIMARY};
            color: {c.BG_BASE};
            border: none;
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 700;
            font-size: {f.SIZE_BODY}px;
        }}

        QCheckBox {{
            color: {c.TEXT_PRIMARY};
            font-size: {f.SIZE_CAPTION}px;
            spacing: 8px;
            background-color: transparent;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {c.BORDER_SUBTLE};
            background-color: {c.BG_SURFACE};
        }}

        QCheckBox::indicator:checked {{
            background-color: {c.ACCENT_PRIMARY};
            border: 1px solid {c.ACCENT_PRIMARY};
        }}

        QToolTip {{
            background-color: {c.BG_SURFACE};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.ACCENT_PRIMARY};
            padding: 4px;
            font-family: "Segoe UI", Tahoma, sans-serif;
            font-size: 12px;
        }}
        """

    @staticmethod
    def badge_style(bg_hex: str, text_hex: str) -> str:
        return (
            f"background-color: {bg_hex};"
            f"color: {text_hex};"
            f"border-radius: 6px;"
            f"padding: 3px 8px;"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            f"font-weight: 700;"
        )