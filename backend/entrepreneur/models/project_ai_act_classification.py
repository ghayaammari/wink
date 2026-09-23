"""Table `project_ai_act_classification` — service 3.3.12 (AI Act). Résultat

du diagnostic de classification de risque : 1 ligne par projet
(UniqueConstraint project_id), toujours créée en `categorie_risque=NULL`
("pas encore diagnostiqué") avant le premier passage de
ai_act_diagnostic_service.run_diagnostic().

Séparée de `project_ai_act_obligations` (décision actée le 19/09/2026,
discussion utilisatrice) : contrairement au RGPD, l'AI Act produit un
verdict unique et distinct par projet (une des 5 catégories du règlement),
pas seulement une liste d'obligations cochables. Fusionner les deux aurait
dupliqué `categorie_risque` sur chaque ligne d'obligation et rendu
impossible d'afficher la catégorie d'un projet "minimal" qui n'a aucune
obligation associée.

`categorie_risque` reprend exactement les 5 valeurs de
`agents/ingestion/legal_text_structuring_service_ai_act.py::CategorieRisqueAIAct`
(même taxonomie que celle utilisée pour classer les articles du corpus, voir
`legal_article_heuristic_classifier_ai_act.py`) — cohérence volontaire entre
la classification d'un article de loi et celle d'un projet.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectAiActClassification(Base):
    __tablename__ = "project_ai_act_classification"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # NULL = diagnostic jamais lancé. Voir CheckConstraint ci-dessous pour les
    # 5 valeurs valides une fois renseigné.
    categorie_risque: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Justification en langage clair, sourcée par le LLM à partir des chunks
    # AI Act fournis (voir agents/compliance_agent/ai_act_service.py) — jamais
    # affichée sans justification, même règle que les obligations RGPD.
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_ai_act_classification_project_id"),
        CheckConstraint(
            "categorie_risque IN ('interdit', 'haut_risque', 'risque_limite', 'gouvernance_gpai', 'minimal')",
            name="ck_project_ai_act_classification_categorie_risque",
        ),
    )
