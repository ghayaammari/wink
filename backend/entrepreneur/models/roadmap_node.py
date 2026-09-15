"""Table `roadmap_nodes` — graphe canonique des étapes de création d'une startup
(service 1.1.x, Groupe 1). Une ligne = une étape, indépendante de tout projet —
`startup_roadmap_items` fait le lien avec un projet précis (voir ce modèle).

Contenu initial chargé depuis `backend/entrepreneur/scripts/data/
wink_roadmap_creation_juridique.json` par `backend/entrepreneur/scripts/
seed_roadmap_nodes.py`, jamais saisi à la main.

`id` en VARCHAR et non UUID (contrairement au reste du schéma Entrepreneur) :
c'est un id métier stable venant du JSON source (ex: "e1_choix_forme_juridique"),
utilisé comme clé d'upsert par le script de seed — un UUID généré empêcherait
de ré-appliquer le JSON de façon idempotente.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class RoadmapNode(Base):
    __tablename__ = "roadmap_nodes"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    groupe: Mapped[str] = mapped_column(String(50), nullable=False)
    # Position d'affichage au sein de la roadmap complète (0..23) — reflète
    # l'ordre du JSON source, pas seulement au sein du groupe. Sans cette
    # colonne, l'ordre d'affichage retombe sur celui de la requête SQL, jamais
    # garanti (voir migration 03ef7cc7d535 et Plan d'action pré-création).
    ordre: Mapped[int] = mapped_column(Integer, nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details_pratiques: Mapped[str | None] = mapped_column(Text, nullable=True)
    administration_liee: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_legale: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Conditions d'applicabilité structurées, ex: {"nb_cofondateurs_gte": 2} — clés lues
    # par le moteur de filtrage de la roadmap par projet (service 1.1.11,
    # roadmap_service._evaluate_applicable_if), pas de schéma fixe ici.
    applicable_if: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    bloquant: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    parallele_avec: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    recommande_avant: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    last_reviewed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # "draft"/"validated" confirmés explicitement (voir plan de seed : tout nœud inséré
        # en "draft", jamais "validated" directement — validation manuelle après relecture).
        CheckConstraint("status IN ('draft', 'validated')", name="ck_roadmap_nodes_status"),
    )
