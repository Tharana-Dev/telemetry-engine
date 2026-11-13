from dataclasses import dataclass

from personalization import current_accent


@dataclass(frozen=True)
class ThemeColors:
    # Surfaces
    BG_BASE: str = "#0F172A"
    BG_SURFACE: str = "#1E293B"
    BG_SURFACE_HOVER: str = "#263349"
    BG_CARD_ACTIVE: str = "#172554"

    # Borders & Dividers
    BORDER_SUBTLE: str = "#334155"
    BORDER_ACCENT: str = "#38BDF8"

    # Typography
    TEXT_PRIMARY: str = "#F8FAFC"
    TEXT_SECONDARY: str = "#94A3B8"
    TEXT_MUTED: str = "#64748B"

    # Telemetry Accents (static fallbacks — live accent comes from personalization)
    ACCENT_PRIMARY: str = "#38BDF8"
    ACCENT_HOVER: str = "#0284C7"
    ACCENT_PRESSED: str = "#0369A1"
    STATUS_OK: str = "#10B981"
    STATUS_WARN: str = "#F59E0B"
    STATUS_ERR: str = "#EF4444"


@dataclass(frozen=True)
class ThemeFonts:
    FAMILY_UI: str = "Segoe UI, Inter, Arial, sans-serif"
    FAMILY_MONO: str = "Consolas, JetBrains Mono, monospace"
    SIZE_HERO: int = 28      # was 20 (The Greeting)
    SIZE_TITLE: int = 20     # was 15 (Laptop Workstation)
    SIZE_BODY: int = 15      # was 13 (Main text, buttons)
    SIZE_CAPTION: int = 13   # was 11 (Subtitles, badges)


class StyleSheets:
    """Centralized Qt Style Sheet (QSS) builders for the application."""

    @staticmethod
    def get_main_stylesheet() -> str:
        """Builds the app-wide QSS, tinted by the user's live accent palette."""
        c = ThemeColors
        f = ThemeFonts
        accent = current_accent()

        return f"""
        /* Base Window & Generic Widgets */
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

        /* Left Telemetry Identity Panel */
        QFrame#IdentityPanel {{
            background-color: {c.BG_SURFACE};
            border: 1px solid {c.BORDER_SUBTLE};
            border-radius: 12px;
        }}

        /* Interactive Telemetry Profile Cards */
        QFrame#ProfileCard {{
            background-color: {c.BG_SURFACE};
            border: 1px solid {c.BORDER_SUBTLE};
            border-radius: 10px;
        }}

        QFrame#ProfileCard:hover {{
            background-color: {c.BG_SURFACE_HOVER};
            border: 1px solid {c.TEXT_MUTED};
        }}

        QFrame#ProfileCard[selected="true"] {{
            background-color: {c.BG_CARD_ACTIVE};
            border: 2px solid {accent.primary};
        }}

        /* Primary Call-to-Action Button */
        QPushButton#PrimaryButton {{
            background-color: {accent.primary};
            color: {c.BG_BASE};
            border: none;
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 700;
            font-size: {f.SIZE_BODY}px;
        }}

        QPushButton#PrimaryButton:hover {{
            background-color: {accent.hover};
            color: {c.TEXT_PRIMARY};
        }}

        QPushButton#PrimaryButton:pressed {{
            background-color: {accent.pressed};
            color: {c.TEXT_PRIMARY};
        }}

        /* Secondary Ghost Button */
        QPushButton#SecondaryButton {{
            background-color: transparent;
            color: {c.TEXT_SECONDARY};
            border: 1px solid {c.BORDER_SUBTLE};
            border-radius: 8px;
            padding: 10px 16px;
            font-weight: 600;
            font-size: {f.SIZE_BODY}px;
        }}

        QPushButton#SecondaryButton:hover {{
            background-color: {c.BG_SURFACE_HOVER};
            color: {c.TEXT_PRIMARY};
            border: 1px solid {c.TEXT_MUTED};
        }}

        QPushButton#SecondaryButton:pressed {{
            background-color: {c.BG_SURFACE};
        }}

        /* CheckBox ("Skip welcome screen next time") */
        QCheckBox {{
            color: {c.TEXT_SECONDARY};
            font-size: {f.SIZE_CAPTION}px;
            spacing: 8px;
            background-color: transparent;
        }}

        QCheckBox:hover {{
            color: {c.TEXT_PRIMARY};
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {c.BORDER_SUBTLE};
            background-color: {c.BG_SURFACE};
        }}

        QCheckBox::indicator:hover {{
            border: 1px solid {accent.primary};
        }}

        QCheckBox::indicator:checked {{
            background-color: {accent.primary};
            border: 1px solid {accent.primary};
        }}
        """

    @staticmethod
    def badge_style(bg_hex: str, text_hex: str) -> str:
        """Returns an inline QSS pill style for status, OS, and privilege badges."""
        return (
            f"background-color: {bg_hex};"
            f"color: {text_hex};"
            f"border-radius: 6px;"
            f"padding: 3px 8px;"
            f"font-family: {ThemeFonts.FAMILY_MONO};"
            f"font-size: {ThemeFonts.SIZE_CAPTION}px;"
            f"font-weight: 700;"
        )