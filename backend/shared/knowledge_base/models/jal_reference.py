"""Table `jal_reference` — référentiel des journaux et services de presse en
ligne (SPEL) habilités à publier des annonces légales, par département
(service 1.1.5 + copilot).

Purement informatif : aucune FK vers `legal_announcements` (l'entrepreneur
publie où il veut, hors Wink). Sert à (1) proposer la liste des journaux du
département du siège sur la page Annonce légale, (2) répondre au copilot
(« quels journaux dans mon département ? ») par requête exacte, jamais par
similarité — donc pas d'embedding de cette table.

Source : registre national actulegales.fr (APTE), vers lequel renvoie
Service-Public (fiche R44934) — une seule source structurée au lieu des ~100
arrêtés préfectoraux annuels. Collecte : `scrapers/jal_reference/` +
`backend/shared/knowledge_base/scripts/collect_jal_reference.py`.

Les habilitations sont ANNUELLES (arrêtés préfectoraux) : recollecter chaque
année ; `derniere_verification` + `actif` évitent d'afficher un journal qui
n'est plus habilité. Insertion toujours en `extrait_automatique` ; seules les
lignes `valide_humain` ET `actif` sont proposées à l'utilisateur.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class JalReference(Base):
    __tablename__ = "jal_reference"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    nom_journal: Mapped[str] = mapped_column(String(255), nullable=False)
    # 'papier' | 'spel'. Déduit du nom à la collecte (heuristique : un nom de
    # domaine = SPEL) — corrigeable à la validation humaine.
    type_support: Mapped[str] = mapped_column(String(10), nullable=False)
    # Codes départements (« 01 », « 2A », « 974 ») — lus par la page Annonce
    # légale à partir du code postal du siège.
    departements_couverts: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    lien_site: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Page de la source d'où la ligne a été extraite (traçabilité).
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        # Clé naturelle de l'upsert : le lien de la fiche du journal sur la
        # source (stable), pas le nom (orthographe variable).
        UniqueConstraint("source_url", name="uq_jal_reference_source_url"),
        CheckConstraint("type_support IN ('papier', 'spel')", name="ck_jal_reference_type_support"),
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_jal_reference_statut_contenu",
        ),
        # Recherche « journaux du département X » (opérateur ANY/@> sur le tableau).
        Index("ix_jal_reference_departements", "departements_couverts", postgresql_using="gin"),
    )
