"""Constantes visuelles du rendu PPTX du pitch deck (service 6.6.2).

Porte depuis le prototype startapini (agents/pitch-deck-agent), inchange :
DEFAULT_ACCENT (indigo-600, #4F46E5) est deja la couleur d'accent utilisee
partout ailleurs dans le frontend Wink (Sidebar, boutons...), donc aucune
reconciliation de charte graphique necessaire.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_BACKGROUND = "0E1B2E"  # dark navy, full-bleed on every slide
CARD_BACKGROUND = "17283F"  # rounded-rect panels: cards, icon-grid tiles
ICON_CIRCLE_BG = "24384F"  # fill behind numbered/glyph icons, distinct from accent
BASE_TEXT_PRIMARY = "FFFFFF"
BASE_TEXT_MUTED = "93A8BE"
DEFAULT_ACCENT = "4F46E5"  # indigo-600, used if a startup has no brand color

TITLE_FONT = "Cambria"  # serif: slide titles, title-slide name, stat callouts
BODY_FONT = "Calibri"  # sans: body text, labels, bullets

SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5


@dataclass(frozen=True)
class ResolvedTheme:
    accent_color: str
    background: str = BASE_BACKGROUND
    card_background: str = CARD_BACKGROUND
    icon_circle_bg: str = ICON_CIRCLE_BG
    text_primary: str = BASE_TEXT_PRIMARY
    text_muted: str = BASE_TEXT_MUTED
    title_font: str = TITLE_FONT
    body_font: str = BODY_FONT


def resolve_theme(accent_color: str | None) -> ResolvedTheme:
    accent = (accent_color or f"#{DEFAULT_ACCENT}").lstrip("#").upper()
    return ResolvedTheme(accent_color=accent)