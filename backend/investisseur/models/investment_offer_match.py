"""Table `investment_offer_matches` — résultat du matching_agent_investisseur

(recherche -> startup, sens inverse de research_need_matches) pour une
offre d'investissement donnée. Même convention que research_need_match.py :
un feed unique par offre (UNIQUE investment_offer_id), régénérer écrase le
résultat précédent, `matches` en JSONB (liste déjà triée par rang) plutôt
qu'une table à part.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class InvestmentOfferMatch(Base):
    __tablename__ = "investment_offer_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    investment_offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_offers.id", ondelete="CASCADE"), nullable=False
    )
    # Liste ordonnée par rang, chaque élément :
    # {project_id, nom, rang, niveau_pertinence, explication, interesse} --
    # voir agents/matching_agent/investisseur_matching_service.py pour le
    # schéma Pydantic exact produit par l'agent.
    matches: Mapped[list] = mapped_column(JSONB, nullable=False)
    synthese: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("investment_offer_id", name="uq_investment_offer_matches_offer_id"),)
