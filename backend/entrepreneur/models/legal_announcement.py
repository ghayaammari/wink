"""Table `legal_announcements` — annonce légale de constitution d'un projet
(service 1.1.5, spec `recap-service-1.1.5-annonce-legale.md`).

Remplace `legal_announcement_transmissions` de la conception Groupe 5 : la
transmission automatique au JAL est hors périmètre (publication payante et
réglementée, aucune voie gratuite — voir DECISIONS.md). Wink rédige, fait
valider, oriente vers les journaux habilités ; l'entrepreneur publie lui-même
puis dépose son attestation. D'où l'absence de colonnes de transmission,
d'erreur ou de tentative.

Cycle de `statut` : `genere` -> `valide_utilisateur` -> `attestation_deposee`.
- Le texte n'est modifiable qu'au statut `genere` (relecture humaine).
- Régénérer repasse à `genere` (tant que l'attestation n'est pas déposée).
- `attestation_deposee` verrouille tout : une annonce publiée ne se corrige
  que par une annonce rectificative (payante), hors périmètre v1.

`UNIQUE(project_id)` : une seule annonce de CONSTITUTION par projet en v1.
⚠️ Évolution : devra sauter (ou devenir `UNIQUE(project_id, type_annonce)`)
quand les annonces de modification (siège, dirigeant...) arriveront.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base

STATUTS_ANNONCE = ("genere", "valide_utilisateur", "attestation_deposee")


class LegalAnnouncement(Base):
    __tablename__ = "legal_announcements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Texte courant : généré, puis éventuellement corrigé par l'entrepreneur
    # (ex. objet social résumé). Considéré fidèle au texte publié.
    texte_annonce: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(30), nullable=False, server_default="genere")
    date_generation: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    date_validation_utilisateur: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Déclaré par l'entrepreneur au dépôt de l'attestation — texte libre, pas
    # de FK vers `jal_reference` : il peut avoir publié dans un journal absent
    # de notre référentiel (qui n'est qu'informatif).
    journal_utilise: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_publication: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Pas de ondelete : l'attestation ne doit pas disparaître silencieusement
    # (même raisonnement que project_legal_profiles.kbis_document_id).
    attestation_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "statut IN ('genere', 'valide_utilisateur', 'attestation_deposee')",
            name="ck_legal_announcements_statut",
        ),
    )
