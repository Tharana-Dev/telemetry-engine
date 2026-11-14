from dataclasses import dataclass

from ui.personalization import current_accent


@dataclass(frozen=True)
class ThemeColors:
    # Surfaces (From the image)
    BG_BASE: str = "#111111"       # Pure Black from image
    BG_SURFACE: str = "#1A1A1A"    # Slightly lighter grey for cards
    BG_SURFACE_HOVER: str = "#262626"
    BG_CARD_ACTIVE: str = "#1F1F1F"

    # Borders & Dividers
    BORDER_SUBTLE: str = "#333333"
    BORDER_ACCENT: str = "#C9EF35"  # Neon Lime

    # Typography
    TEXT_PRIMARY: str = "#F8FAFC"
    TEXT_SECONDARY: str = "#A1A1AA"
    TEXT_MUTED: str = "#71717A"

    # Telemetry Accents (Use the Lime and Pink!)
    ACCENT_PRIMARY: str = "#C9EF35" # Neon Lime
    ACCENT_HOVER: str = "#B5D82A"
    ACCENT_PRESSED: str = "#9EBF1E"
    
    STATUS_OK: str = "#C9EF35"      # Lime for OK
    STATUS_WARN: str = "#FFD700"
    # Gold for warning
    STATUS_ERR: str = "#FF2B93"     # Hot Pink for Errors!


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
        
        /* Retro Windows Tooltips */
        QToolTip {{
            background-color: #FFFFE1;
            color: #000000;
            border: 1px solid #000000;
            padding: 2px;
            font-family: "Segoe UI", Tahoma, sans-serif;
            font-size: 12px;
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