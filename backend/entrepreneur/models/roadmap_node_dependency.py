"""Table `roadmap_node_dependencies` — arêtes du graphe `roadmap_nodes` (quel

nœud dépend de quel autre, JSON source : champ `depends_on`). Clé primaire
composite, pas de colonne `id` séparée — une paire (node_id, depends_on_node_id)
n'a de sens qu'une seule fois.
"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class RoadmapNodeDependency(Base):
    __tablename__ = "roadmap_node_dependencies"

    node_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("roadmap_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_node_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("roadmap_nodes.id", ondelete="CASCADE"), primary_key=True
    )
