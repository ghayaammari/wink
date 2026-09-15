"""Schémas Pydantic pour le service "Plan d'action pré-création" (roadmap
d'EPIC-01) — `startup_roadmap_items`, enrichi des colonnes `groupe`/`ordre` de
`roadmap_nodes` (live, pas figées comme `node_snapshot`) et de l'URL de la
preuve jointe le cas échéant.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

# "verrouille" volontairement absent des valeurs settables par le client
# (RoadmapItemUpdate ci-dessous) : c'est roadmap_service qui le pose/le lève,
# jamais une action utilisateur directe — voir _cascade_unlock.
RoadmapItemStatut = Literal["verrouille", "a_faire", "en_cours", "termine", "non_necessaire"]
RoadmapItemSettableStatut = Literal["a_faire", "en_cours", "termine", "non_necessaire"]


class RoadmapItemRead(BaseModel):
    id: UUID
    project_id: UUID
    node_id: str
    # Live depuis roadmap_nodes, pas depuis node_snapshot : la position/le
    # regroupement sont structurels, pas du contenu figé au sens du
    # commentaire de node_snapshot (voir startup_roadmap_item.py).
    groupe: str
    ordre: int
    statut: RoadmapItemStatut
    node_snapshot: dict
    # Live depuis roadmap_node_dependencies, même raison que groupe/ordre —
    # jamais figé dans node_snapshot. Prérequis directs uniquement (pas les
    # nœuds débloqués par celui-ci) : suffisant pour reconstruire les flèches
    # de dépendance et la liste "Étapes requises" côté frontend, sans avoir à
    # exposer aussi les dépendants.
    depends_on: list[str]
    proof_document_id: UUID | None
    proof_document_url: str | None
    assigned_at: datetime
    completed_at: datetime | None


class RoadmapItemUpdate(BaseModel):
    statut: RoadmapItemSettableStatut
