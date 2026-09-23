"""Table `project_fintech_gap_analysis` — service 3.3.6 (diagnostic d'écart),

volet FinTech. Contrairement à `project_healthtech_gap_analysis` (1 ligne
PAR chapitre, 3 chapitres séquentiels), FinTech n'a qu'UN SEUL bloc légal
collecté (Code monétaire et financier, Chapitre II — établissements de
paiement, voir scrapers/legifrance/blocs_secteur_fintech.py) : pas de
découpage naturel en étapes, donc 1 seule ligne par projet, jamais plusieurs
— décision actée le 20/09/2026 ("celle qui nécessite un roadmap on la fait,
si non ce n'est pas la peine de faire une roadmap").

Comme pour HealthTech, pas de champ `statut` : la ligne existe (générée) ou
n'existe pas (pas encore générée) — le statut se déduit à la lecture, jamais
stocké. Génération déclenchée uniquement par un clic explicite (jamais
automatique), même raisonnement que HealthTech : un vrai appel LLM+RAG
coûteux, à la différence du calcul déterministe gratuit de la classification.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectFintechGapAnalysis(Base):
    __tablename__ = "project_fintech_gap_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Même forme que project_healthtech_gap_analysis.obligations (liste sous
    # clé "obligations", cohérence entre les 2 volets du service 3.3.6).
    obligations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("project_id", name="uq_project_fintech_gap_analysis_project_id"),)
