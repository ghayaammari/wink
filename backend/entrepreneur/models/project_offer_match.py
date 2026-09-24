"""Table `project_offer_matches` — résultat du matching_agent_startup

(Startup -> Offres, sens inverse de investment_offer_matches) pour LE
PROJET de l'entrepreneur connecté. Placée cote entrepreneur (et non dans
backend/matching/, pourtant prevu par l'architecture pour le cross-acteur)
pour rester coherente avec investment_offer_match.py, deja place cote
investisseur (a cote de l'entite dont son FK depend) -- decision actee le
24/09/2026 plutot que de melanger 2 conventions differentes pour la meme
fonctionnalite tant que l'existant n'est pas corrige.

Meme convention que investment_offer_match.py : un feed unique par PROJET
(UNIQUE project_id, pas de notion de "besoin" intermediaire comme
research_needs -- un projet n'a qu'un feed d'offres, pas un feed par
besoin), regenerer ecrase le resultat precedent, `matches` en JSONB (liste
deja triee par rang) plutot qu'une table a part.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectOfferMatch(Base):
    __tablename__ = "project_offer_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Liste ordonnée par rang, chaque élément (produit par l'agent, jamais
    # enrichi ici) : {offer_id, rang, niveau_pertinence, explication,
    # interesse} -- voir agents/matching_agent/startup_offer_matching_
    # service.py pour le schéma Pydantic exact. Les champs vivants de
    # l'offre (titre, montant, secteurs, statut...) sont lus en direct a la
    # lecture (project_offer_match_service.py::_enrichir_matches), jamais
    # stockes ici -- meme raisonnement que cote investisseur (StartupMatchRead).
    matches: Mapped[list] = mapped_column(JSONB, nullable=False)
    synthese: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("project_id", name="uq_project_offer_matches_project_id"),)
