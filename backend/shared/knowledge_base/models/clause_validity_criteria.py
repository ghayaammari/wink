"""Table `clause_validity_criteria` — critères de conformité attachés à une clause
type (Phase collecte, Groupe 5 — services 1.1.13 / 1.1.4).

Une clause peut avoir plusieurs critères (ex: durée maximale, contrepartie
financière requise). Volontairement NON vectorisée : ce sont des règles
structurées, lues par jointure directe (clause_library_id), jamais par recherche
sémantique — le dépassement d'un seuil (`valeur_limite`) se détecte par du code
déterministe au moment de la génération, pas par similarité.

`valeur_limite` en JSONB libre (ex: {"unite": "mois", "max": 24}) plutôt que des
colonnes typées : les critères à venir seront hétérogènes (durées, montants,
ratios) et ne justifient pas un schéma figé aujourd'hui.
(réalisé par OPENCODE)
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ClauseValidityCriterion(Base):
    __tablename__ = "clause_validity_criteria"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # ondelete CASCADE : les critères appartiennent à leur clause, la supprimer
    # supprimerait des critères sans propriétaire (conformité ≠ donnée réutilisable).
    clause_library_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses_library.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_critere: Mapped[str] = mapped_column(String(80), nullable=False)
    description_critere: Mapped[str] = mapped_column(Text, nullable=False)
    valeur_limite: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    base_legale: Mapped[str] = mapped_column(Text, nullable=False)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")

    __table_args__ = (
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_clause_validity_criteria_statut_contenu",
        ),
    )