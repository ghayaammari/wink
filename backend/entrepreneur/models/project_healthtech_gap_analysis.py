"""Table `project_healthtech_gap_analysis` — service 3.3.6 (diagnostic
d'écart), volet HealthTech. Une ligne = un chapitre du parcours pour un
projet donné, avec son résultat (obligations identifiées) une fois généré.

Contrairement à `project_healthtech_classification` (1 ligne par projet,
recalculée à chaque PATCH), cette table a 1 ligne PAR (projet, chapitre) —
plusieurs chapitres distincts à traiter séquentiellement (voir
healthtech_gap_analysis_chapitres.py pour la liste et l'ordre). Pas de champ
`statut` : contrairement à `startup_roadmap_items.statut` (EPIC-01, tâche
manuelle sans donnée sous-jacente), ici le statut d'un chapitre se déduit
directement de la présence ou non de sa ligne dans cette table — une ligne
existe = chapitre traité, pas de ligne = chapitre pas encore traité. Le
déblocage (chapitre suivant accessible) se calcule aussi à la lecture (voir
project_healthtech_gap_analysis_service.py), jamais stocké ici.

Génération déclenchée UNIQUEMENT par un clic explicite sur le chapitre
correspondant côté frontend (jamais automatique, contrairement à la
classification qui se recalcule à chaque PATCH) — décision actée le
20/09/2026 : chaque chapitre implique un vrai appel LLM + RAG coûteux, à la
différence de `classify()` qui est un calcul Python gratuit et instantané.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectHealthtechGapAnalysis(Base):
    __tablename__ = "project_healthtech_gap_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Valeurs fixées par healthtech_gap_analysis_chapitres.py (registre en
    # code, pas une table de catalogue séparée — 3 chapitres fixes, pas de
    # besoin d'un catalogue éditable, voir docstring de ce fichier).
    chapitre: Mapped[str] = mapped_column(Text, nullable=False)
    # Liste structurée des obligations/écarts identifiés pour ce chapitre —
    # JSONB plutôt que Text libre : permet d'afficher une liste de cartes
    # côté frontend (comme project_rgpd_obligations) sans reparser du texte.
    obligations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "chapitre", name="uq_project_healthtech_gap_analysis_project_chapitre"),
        CheckConstraint(
            "chapitre IN ('obligations_fabricant', 'evaluation_clinique', 'surveillance_post_commercialisation')",
            name="ck_project_healthtech_gap_analysis_chapitre",
        ),
    )
