"""Réexporte toutes les tables du corpus copilot — obligatoire pour qu'Alembic les détecte."""
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings
from backend.shared.knowledge_base.models.legal_texts import LegalText
from backend.shared.knowledge_base.models.sector_insurance_recommendations import SectorInsuranceRecommendation

__all__ = ["ContentEmbeddings", "LegalText", "SectorInsuranceRecommendation"]
