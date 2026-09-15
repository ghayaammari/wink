"""Table `legal_texts` — corpus de textes réglementaires sourcés (Groupe 2),
premier consommateur : service 1.1.1 (forme juridique). Une ligne = un article
de loi (ou équivalent : loi non codifiée, disposition CGI...) jugé pertinent
pour un entrepreneur, avec sa classification pour le copilot.

Alimentée par `backend/shared/knowledge_base/scripts/
collect_legal_texts_formes_juridiques.py` (Phase 1 du plan Notion) — jamais
saisie à la main. Toute ligne insérée l'est en `statut_contenu='extrait_automatique'`
(jamais directement en `valide_humain`, voir cette colonne ci-dessous) : la
validation humaine est un dashboard séparé, pas encore construit (voir ce script).

`synthese` volontairement absente de ce schéma (retirée par décision explicite,
contrairement au schéma Notion d'origine) : seul `texte_brut` est vectorisé pour
le copilot (voir `content_embeddings.champ_source`), une synthèse reformulée
n'a pas d'usage actuel — à réintroduire seulement si un vrai besoin d'affichage
"version courte" apparaît.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class LegalText(Base):
    __tablename__ = "legal_texts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    domaine_reglementaire: Mapped[str] = mapped_column(String(50), nullable=False)
    code_source: Mapped[str] = mapped_column(String(150), nullable=False)
    article_numero: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sous_theme: Mapped[str | None] = mapped_column(String(50), nullable=True)
    forme_juridique_concernee: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    chunking_suggere: Mapped[str] = mapped_column(String(20), nullable=False, server_default="aucun")
    texte_brut: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_effet: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_derniere_modification: Mapped[date | None] = mapped_column(Date, nullable=True)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("code_source", "article_numero", name="uq_legal_texts_code_article"),
        CheckConstraint("statut_contenu IN ('extrait_automatique', 'valide_humain')", name="ck_legal_texts_statut_contenu"),
        CheckConstraint("chunking_suggere IN ('aucun', 'par_alinea')", name="ck_legal_texts_chunking_suggere"),
    )
