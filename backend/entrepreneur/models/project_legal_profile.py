"""Table `project_legal_profiles` — identité légale du projet (pour les startups déjà créées).

Vérification I1 Groupe 4 (voir "Wink — Schémas Incrément 1 v3" + page Notion
"Schemas grp 4") : `is_registered`/`verification_status` (un seul statut global)
retirés, remplacés par 3 statuts séparés selon l'événement qui produit la
donnée (dénomination / immatriculation / Kbis) — voir migration 4fa5a487a845.

Groupe 5 (migration e1b2c3d4e5f6) : `legal_representative` (JSONB) supprimé,
remplacé par `legal_representative_associate_id` (FK → project_associates.id,
NULLABLE — le représentant légal n'est désigné qu'une fois les statuts rédigés,
voir Groupe5_doc.md). Ajout d'`objet_social`/`duree_societe`/
`date_signature_statuts` : faits uniques par projet, nécessaires aux statuts
(1.1.4) ET à l'annonce légale (1.1.5). (réalisé par OPENCODE)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

# Valeurs actées (voir "Schemas grp 4") pour les 3 statuts de vérification
# ci-dessous — mêmes valeurs partout, pas un enum par colonne.
_VERIFICATION_STATUTS = "('non_verifie', 'verifie', 'incoherent')"


class ProjectLegalProfile(Base):
    __tablename__ = "project_legal_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(120), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True, index=True)
    siret: Mapped[str | None] = mapped_column(String(14), nullable=True, index=True)
    vat_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    naf_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registered_address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Le représentant légal est un associé précis (personne physique), pointé
    # par FK après rédaction des statuts (1.1.4) — NULL auparavant.
    # NOT NULL une fois la société immatriculée (contrainte applicative : la
    # désignation intervenant au dépôt, avant immatriculation e13→e16).
    legal_representative_associate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_associates.id", ondelete="SET NULL"), nullable=True
    )
    # Faits uniques par projet, produits par 1.1.4, consommés aussi par 1.1.5.
    objet_social: Mapped[str | None] = mapped_column(Text, nullable=True)
    duree_societe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_signature_statuts: Mapped[date | None] = mapped_column(Date, nullable=True)
    # AJOUT (migration f5a7c9e1d3b2, service 1.1.4 statuts SAS -- catégorie B2 de
    # l'inventaire des 210 variables, historique "avant de valider" 22/09/2026).
    # Faits juridiques de la société, volontairement PAS dans project_public_profiles
    # (table de vitrine/matching : public_summary est un pitch modifiable, ces textes
    # sont des engagements statutaires imprimés dans les statuts -- même analyse que
    # Groupe5_doc.md pour objet_social/duree_societe).
    raison_d_etre: Mapped[str | None] = mapped_column(Text, nullable=True)
    objectifs_ess: Mapped[str | None] = mapped_column(Text, nullable=True)
    sigle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lieu_signature_statuts: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # AJOUT (migration 507ed2995d84, service 1.1.13) -- 4 faits fixes du
    # projet consommés par le Préambule du pacte de fondateurs, absents
    # jusqu'ici. Distinct des colonnes homonymes sur `project_associates`
    # (`capital_social`/`lieu_immatriculation`) : celles-ci décrivent LE
    # PROJET lui-même, celles de `project_associates` décrivent un associé
    # qui est une personne morale -- même nom, table différente, ne pas
    # confondre en code review.
    capital_social: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    lieu_immatriculation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nombre_actions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valeur_nominale: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Rempli uniquement par upload manuel de l'utilisateur (service 1.1.9/Parcours),
    # jamais par un job automatique — voir "Schemas grp 4". Pas de ondelete ici :
    # un document ne doit pas disparaître silencieusement de ce profil.
    kbis_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    denomination_verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="non_verifie"
    )
    immatriculation_verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="non_verifie"
    )
    kbis_verification_status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="non_verifie"
    )
    # Rempli une seule fois au dépôt (e13), lu en boucle par le job Guichet Unique
    # jusqu'à e16, puis inutile — jamais affiché à l'utilisateur (voir Parcours A).
    numero_suivi_formalite: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"denomination_verification_status IN {_VERIFICATION_STATUTS}",
            name="ck_project_legal_profiles_denomination_verification_status",
        ),
        CheckConstraint(
            f"immatriculation_verification_status IN {_VERIFICATION_STATUTS}",
            name="ck_project_legal_profiles_immatriculation_verification_status",
        ),
        CheckConstraint(
            f"kbis_verification_status IN {_VERIFICATION_STATUTS}",
            name="ck_project_legal_profiles_kbis_verification_status",
        ),
    )
