"""Réexporte toutes les tables du domaine Chercheur — obligatoire pour qu'Alembic les détecte."""
from backend.chercheur.models.researcher_profile import ResearcherProfile

__all__ = ["ResearcherProfile"]
