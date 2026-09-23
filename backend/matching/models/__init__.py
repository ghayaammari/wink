"""Réexporte toutes les tables du domaine Matching (cross-acteurs) — obligatoire pour qu'Alembic les détecte."""
from backend.matching.models.research_need import ResearchNeed
from backend.matching.models.research_need_match import ResearchNeedMatch

__all__ = [
    "ResearchNeed",
    "ResearchNeedMatch",
]
