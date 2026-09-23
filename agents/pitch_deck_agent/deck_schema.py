"""Schema strict du contenu d'un pitch deck (service 6.6.2) — sortie exigee

de pitch_deck_content_service.py, et seule entree de
backend/entrepreneur/services/pitch_deck_renderer_service.py (le renderer
PPTX ne lit jamais de JSON brut du LLM, seulement ce modele valide).

Porte depuis le prototype startapini (agents/pitch-deck-agent), simplifie :
- Pas de bilingue FR/EN (chaque champ un `LocalizedText {fr, en}` chez
  startapini) : une seule chaine francaise par champ, decision produit du
  21/09/2026 (Wink reste France uniquement pour l'instant). Rajouter l'anglais
  plus tard ne casse pas ce schema : un `str` peut redevenir `{fr, en}` sans
  toucher aux 11 diapositives elles-memes.
- Pas de `target_audience` (startapini prevoyait investor/incubator/hackathon
  en plus de "public" — non demande ici, un seul type de deck pour l'instant).
- Pas de field_validator "meme nombre de puces FR/EN" (n'a plus de sens en
  monolingue).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

MAX_BULLETS = 4
MAX_BULLET_LEN = 140
MAX_TITLE_LEN = 80
MAX_PARAGRAPH_LEN = 400


class TitleSlide(BaseModel):
    startup_name: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    one_liner: str = Field(..., min_length=1, max_length=MAX_PARAGRAPH_LEN)


class ProblemSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class SolutionSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class MarketStat(BaseModel):
    value: str = Field(..., min_length=1, max_length=32)
    label: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)


class MarketSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)
    stat: MarketStat | None = None
    # Chiffre de croissance/momentum optionnel (ex: "+18% YoY"), affiche comme
    # badge separe de `stat` -- voir SYSTEM_PROMPT pour la consigne "ne pas
    # dupliquer ce chiffre dans une puce".
    highlight: MarketStat | None = None


class BusinessModelSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class CompetitionSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class FinancialsSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class RoadmapSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class TractionMetric(BaseModel):
    label: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    value: str = Field(..., min_length=1, max_length=32)


class TractionMilestone(BaseModel):
    date: str = Field(..., min_length=1, max_length=32)
    label: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)


class TractionSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    metrics: list[TractionMetric] = Field(default_factory=list, max_length=4)
    milestones: list[TractionMilestone] = Field(default_factory=list, max_length=5)


class TeamMember(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    role: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    photo_url: str | None = None


class TeamSlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    members: list[TeamMember] = Field(..., min_length=1, max_length=8)


class CTASlide(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    ask_summary: str = Field(..., min_length=1, max_length=MAX_PARAGRAPH_LEN)
    bullets: list[str] = Field(..., min_length=1, max_length=MAX_BULLETS)


class DeckSlides(BaseModel):
    title: TitleSlide
    problem: ProblemSlide
    solution: SolutionSlide
    market: MarketSlide
    business_model: BusinessModelSlide
    competition: CompetitionSlide
    traction: TractionSlide
    team: TeamSlide
    financials: FinancialsSlide
    roadmap: RoadmapSlide
    cta: CTASlide


class BrandTheme(BaseModel):
    """Habillage visuel — pas de champ couleur par projet pour l'instant

    (pas demande, evite un selecteur de couleur en plus dans le formulaire) :
    accent_color reste la couleur Wink par defaut, voir DEFAULT_ACCENT dans
    pitch_deck_renderer_service.py. Seul le logo varie, relu depuis
    ProjectPublicProfile.logo_url (voir pitch_deck_service.py)."""

    accent_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    logo_url: str | None = None


class DeckContentModel(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(..., min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    brand: BrandTheme
    slides: DeckSlides
