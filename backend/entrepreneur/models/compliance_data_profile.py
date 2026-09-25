"""Table `compliance_data_profile` — service 3.3.1 (RGPD). Profil des
traitements de données d'un projet : PAS capturé à l'onboarding (I0), mais à
la première visite de la carte "Conformité > RGPD" — décision actée après
discussion (timing/précision : le profil doit refléter l'usage réel des
données, pas une intention déclarée trop tôt ; voir aussi séparation des
responsabilités onboarding vs diagnostic conformité).

1 ligne par projet (UniqueConstraint project_id). Champs nullable : la ligne
peut être créée dès l'accès à la carte RGPD avant que l'entrepreneur ait
répondu à toutes les questions du diagnostic — NULL = "pas encore répondu",
distinct de False (même convention que `projects.description`/`sector`,
nullable pour représenter un état transitoire réel, voir ce modèle).

Ne duplique PAS `projects.sector` (déjà présent) — uniquement les questions
propres au diagnostic RGPD, absentes du profil projet général.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ComplianceDataProfile(Base):
    __tablename__ = "compliance_data_profile"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Art. 9 RGPD (catégories particulières : santé, biométrie, origine,
    # opinions...) — détermine si un régime renforcé (AIPD quasi systématique)
    # s'applique.
    collecte_donnees_sensibles: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    collecte_donnees_mineurs: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Matching/personnalisation/scoring automatisé — voir exemple d'usage
    # discuté : détermine si le projet fait du profilage au sens RGPD.
    profilage: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Sous-traitants/outils tiers (hébergeur, emailing, analytics...) — Art. 28
    # RGPD (contrats de sous-traitance). Ajouté suite à la revue du schéma
    # (gap identifié : obligation Art. 28 sinon non couverte par le profil).
    partage_avec_tiers: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    transfert_hors_ue: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_compliance_data_profile_project_id"),
    )
