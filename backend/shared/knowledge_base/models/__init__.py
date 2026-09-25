"""Réexporte toutes les tables du corpus copilot — obligatoire pour qu'Alembic les détecte."""
from backend.shared.knowledge_base.models.article_explication import ArticleExplication
from backend.shared.knowledge_base.models.clause_validity_criteria import ClauseValidityCriterion
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary
from backend.shared.knowledge_base.models.document_template import DocumentTemplate
from backend.shared.knowledge_base.models.jal_reference import JalReference
from backend.shared.knowledge_base.models.legal_announcement_guides import LegalAnnouncementGuide
from backend.shared.knowledge_base.models.legal_texts import LegalText
from backend.shared.knowledge_base.models.sector_insurance_recommendations import SectorInsuranceRecommendation

__all__ = [
    "ArticleExplication",
    "ContentEmbeddings",
    "LegalText",
    "SectorInsuranceRecommendation",
    "ContractClauseLibrary",
    "ClauseValidityCriterion",
    "DocumentTemplate",
    "JalReference",
    "LegalAnnouncementGuide",
]
