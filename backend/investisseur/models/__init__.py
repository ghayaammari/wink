"""Réexporte toutes les tables du domaine Investisseur — obligatoire pour qu'Alembic les détecte."""
from backend.investisseur.models.investor_profile import InvestorProfile

__all__ = ["InvestorProfile"]
