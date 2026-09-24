"""Table `article_explications` — explication en langage clair d'un article
facultatif, affichée sur l'écran de choix des facultatifs (service 1.1.4,
étape 4 de la refonte du parcours, 24/09/2026).

Contenu de référence (même famille que `contract_clauses_library`) : généré en
batch par le LLM (`agents/contract_agent/article_explanation_service.py`,
script `backend/entrepreneur/scripts/generate_statuts_article_explanations.py`)
puis RELU par un humain. Seules les lignes `valide_humain` sont affichées ;
sinon l'écran garde le texte provisoire de `FACULTATIFS_STATUTS`.

Clé = `code_facultatif` (le CHOIX de l'écran, ex. `droit_preemption`,
`directeurs_generaux`), pas un numéro d'article : un choix peut regrouper
plusieurs articles (Directeur Général = Art. 23 + 40).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ArticleExplication(Base):
    __tablename__ = "article_explications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Même convention que contract_clauses_library : pas de CHECK sur la liste
    # des document_type (encore évolutive).
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    code_facultatif: Mapped[str] = mapped_column(String(80), nullable=False)
    texte: Mapped[str] = mapped_column(Text, nullable=False)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    genere_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valide_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("document_type", "code_facultatif", name="uq_article_explications_document_code"),
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_article_explications_statut_contenu",
        ),
    )
