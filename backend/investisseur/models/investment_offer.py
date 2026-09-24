"""Table `investment_offers` — offre d'investissement déposée par un

investisseur (EPIC-07, volet Investisseur -> Startup du matching, miroir de
`research_needs` côté entrepreneur -> chercheur). Un investisseur peut
déposer plusieurs offres ; chacune est la base d'un feed de matching
indépendant vers les startups de la plateforme (voir investment_offer_
match.py), même raisonnement que ResearchNeed/ResearchNeedMatch.

Contrairement à research_needs (titre + description libre uniquement),
cette offre porte aussi des champs structurés (montant, secteurs/stades
ciblés) : décision produit du 24/09/2026 — un investisseur raisonne
naturellement par montant et critères de ciblage, pas seulement par texte
libre, et ces champs permettent au matching_agent_investisseur de filtrer
plus précisément qu'une simple recherche sémantique sur la description.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class InvestmentOffer(Base):
    __tablename__ = "investment_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    investor_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investor_profiles.id", ondelete="CASCADE"), nullable=False
    )
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Euros, montant unique proposé (pas de min/max séparés -- décision
    # produit du 24/09/2026, simplicité du formulaire de dépôt).
    montant_propose: Mapped[int] = mapped_column(Integer, nullable=False)
    # Listes de chaînes libres (mêmes valeurs que Project.sector côté
    # entrepreneur, mais pas contraint ici -- l'investisseur peut cibler un
    # secteur qui n'existe pas encore comme valeur de projet, ex. "climat").
    secteurs_cibles: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Sous-ensemble libre des valeurs Project.stage ('ideation', 'pre_seed',
    # 'seed', 'serie_a') -- pas de CheckConstraint dessus : une liste vide
    # signifie "tous les stades", pas une valeur invalide.
    stades_cibles: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # 'ouvert' = un feed de matching est calculé pour cette offre. 'ferme' =
    # l'investisseur a conclu ou abandonné -- l'offre reste visible
    # (historique) mais ne doit plus être relancée -- même convention que
    # ResearchNeed.statut.
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ouvert")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("montant_propose > 0", name="ck_investment_offers_montant_propose_positif"),
        CheckConstraint("statut IN ('ouvert', 'ferme')", name="ck_investment_offers_statut"),
    )
