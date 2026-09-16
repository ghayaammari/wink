"""Table `contract_clauses_library` — bibliothèque de clauses contractuelles types
(Phase collecte, Groupe 5 — services 1.1.13 pacte de fondateurs / 1.1.4 statuts).

Une ligne = une clause type prête à être injectée dans un document, partagée
entre tous les documents-contrats (pacte, statuts, futurs nda/cession_ip en I2).
Contenu de référence externe, jamais saisi à la main : alimenté par le pipeline
de collecte dédié (mêmes sources stables, ex. Bpifrance Création).

Deux usages distincts, d'où les deux champs textuels adjacents :
- `scenario_description` sert à MATCHER l'intention utilisateur (vectorisé dans
  `content_embeddings`, champ_source='scenario_description') ;
- `texte_clause` est le CONTENU final injecté dans le document (vectorisé aussi,
  champ_source='texte_clause', mais pour servir le copilot, pas le matcher).

Le retrieval ne sert que les lignes en `statut_contenu='valide_humain'` : toute
ligne insérée par collecte automatique est inutilisable tant qu'une validation
humaine ne l'a pas passée — contrainte applicative, pas de flag distinct.
(réalisé par OPENCODE)
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ContractClauseLibrary(Base):
    __tablename__ = "contract_clauses_library"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Valeurs fermées évolutives : 'pacte_fondateurs', 'statuts' (I1), futurs 'nda'/'cession_ip' (I2).
    # Pas de CHECK constraint volontairement : le document_type voyage aussi dans
    # contract_clauses_library et content_embeddings avec chacun sa propre contrainte —
    # on attend I2 pour figer la liste complète.
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    scenario: Mapped[str] = mapped_column(String(80), nullable=False)
    scenario_description: Mapped[str] = mapped_column(Text, nullable=False)
    titre_clause: Mapped[str] = mapped_column(String(255), nullable=False)
    # Template de clause avec variables à injecter (voir variables_requises) — enrichi
    # au moment de la génération par les données du projet (project_associates, etc.).
    texte_clause: Mapped[str] = mapped_column(Text, nullable=False)
    variables_requises: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_modele: Mapped[str] = mapped_column(String(120), nullable=False)
    verifie_par_professionnel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    forme_juridique_concernee: Mapped[str | None] = mapped_column(String(60), nullable=True)
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")

    __table_args__ = (
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_contract_clauses_library_statut_contenu",
        ),
    )