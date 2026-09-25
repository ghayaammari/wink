"""Table `document_generation_variable_values` — instantané figé des variables
injectées dans un document généré (Groupe 5, service 1.1.13 — pacte de
fondateurs v2 ; réutilisable par 1.1.4/statuts comme le reste du moteur).

Rempli uniquement à la finalisation (`finalize_session`), jamais pendant la
session en cours : `document_generation_sessions.reponses` reste la seule
source de vérité tant que la session n'est pas terminée. Cette table sert
uniquement à consulter/modifier une variable précise d'un document déjà
généré, sans avoir à rejouer toute la session.

Rattachée à `document_versions.id` (pas `documents.id`) : une future
re-finalisation (nouvelle version du même document) garde l'instantané de
l'ancienne version intact plutôt que de l'écraser.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class DocumentGenerationVariableValue(Base):
    __tablename__ = "document_generation_variable_values"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # code_section de document_templates dont provient cette variable.
    code_section: Mapped[str] = mapped_column(String(255), nullable=False)
    # code_clause de contract_clauses_library — NULL pour les variables des
    # sections donnee_projet (identification_des_parties), qui ne référencent
    # aucune clause.
    code_clause: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nom_variable: Mapped[str] = mapped_column(String(120), nullable=False)
    type_variable: Mapped[str] = mapped_column(String(30), nullable=False)
    valeur: Mapped[str | None] = mapped_column(Text, nullable=True)
    # false pour les variables résolues automatiquement (auto_*, reference_croisee,
    # données associé) — distingue une saisie de l'entrepreneur d'une valeur
    # déduite par le moteur, utile si l'affichage futur veut les traiter différemment.
    saisie_manuellement: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "code_section", "nom_variable",
            name="uq_document_generation_variable_values_version_section_variable",
        ),
    )
