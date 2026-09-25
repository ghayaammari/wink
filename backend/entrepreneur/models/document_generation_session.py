"""Table `document_generation_sessions` — état de la session interactive de
génération guidée d'un document (Groupe 5, Phase mécanisme manquante).

Comble un trou du schéma spécifié : `Groupe5_doc.md` ne documente une "Phase
mécanisme" que pour 1.1.6/1.1.5/1.1.7/1.1.8, jamais pour 1.1.13 (pacte) ni
1.1.4 (statuts) — rien ne précisait où stocker l'avancement de la session
(section courante, variante de clause choisie, réponses en brouillon) ni le
document final généré. Décision actée avec l'utilisateur (session du
20/09/2026) : une nouvelle table dédiée, plutôt que de détourner
`project_field_values` (pensée pour des champs individuels, pas pour une
session de génération de document en plusieurs étapes).

Générique dès maintenant (`document_type`, même liste que
`contract_clauses_library`/`document_templates`) et non `founder_pact_sessions` :
1.1.4 (statuts) partage déjà les mêmes tables de Phase collecte (clauses,
squelette de document) et aura le même besoin de session interactive — créer
une table par service dupliquerait exactement la même structure une seconde
fois dans quelques semaines.

Pas de CHECK sur `document_type` (même raisonnement que
`contract_clauses_library.document_type`, voir migration c1d2e3f4a5b6) :
liste évolutive (statuts, futurs nda/cession_ip en I2), figée quand le besoin
de contrainte stricte apparaîtra réellement.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class DocumentGenerationSession(Base):
    __tablename__ = "document_generation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="en_cours")
    # code_section de document_templates en cours de traitement (NULL une fois
    # `statut='complete'`) — pilote quel écran/question le frontend affiche.
    section_courante: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Une clé par code_section déjà traitée : {"<code_section>": {"variante":
    # "<code_clause contract_clauses_library>", "valeurs": {...}, "inclus": bool}}.
    # "inclus" ne s'applique qu'aux sections facultatives (garde une trace du
    # refus explicite, pour ne jamais reposer la question au rechargement).
    reponses: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    # Rempli seulement à la finalisation (étape 5 du scénario) — pas de
    # ondelete : un document généré ne doit pas disparaître silencieusement
    # si la session est reprise/recréée (même raisonnement que
    # project_legal_profiles.kbis_document_id).
    document_genere_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Une session active par (projet, type de document) : pas deux pactes
        # en cours de rédaction en parallèle pour le même projet.
        UniqueConstraint("project_id", "document_type", name="uq_document_generation_sessions_project_type"),
        CheckConstraint("statut IN ('en_cours', 'complete')", name="ck_document_generation_sessions_statut"),
    )
