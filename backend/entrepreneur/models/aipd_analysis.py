"""Table `aipd_analyses` — service 3.3.4 (AIPD), déclenché depuis l'intérieur
de la carte RGPD (3.3.1), pas une roadmap à part : générateur one-shot,
comme actée dans la classification finale des services EPIC-03.

Lié à l'obligation AIPD via `project_rgpd_obligation_id` (nullable : l'AIPD
peut en théorie être régénérée même si la ligne d'obligation associée a été
recréée entre-temps par l'agent — pas de garantie de continuité, voir
project_rgpd_obligation.py sur la fragilité assumée du matching par nom).

MVP : `contenu` est le document généré tel quel (texte), pas encore structuré
en sections éditables séparément — à revoir seulement si un vrai besoin
d'édition section par section apparaît côté frontend (pas demandé à ce stade).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class AipdAnalysis(Base):
    __tablename__ = "aipd_analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    project_rgpd_obligation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_rgpd_obligations.id", ondelete="SET NULL"), nullable=True
    )
    contenu: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
