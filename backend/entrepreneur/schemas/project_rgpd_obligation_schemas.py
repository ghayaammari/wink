"""Schémas Pydantic pour `project_rgpd_obligations` — service 3.3.1 (RGPD)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# Seul "statut" est settable par le client (case à cocher) — nom/description/
# legal_text_id ne sont écrits que par sync_obligations (compliance_agent via
# le service), jamais par une édition libre de l'entrepreneur.
ObligationStatut = Literal["a_faire", "fait"]


class ProjectRgpdObligationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    nom: str
    description: str
    statut: ObligationStatut
    legal_text_id: UUID | None
    # Regroupement demande le 17/09/2026 : permet au frontend d'afficher les
    # obligations liees a une AIPD a part du reste, sans deviner via un
    # matching texte fragile sur nom/description.
    lie_a_aipd: bool
    created_at: datetime
    updated_at: datetime


class ProjectRgpdObligationStatutUpdate(BaseModel):
    statut: ObligationStatut


class RgpdObligationCandidate(BaseModel):
    """Une obligation proposée par le compliance_agent, avant passage dans

    `sync_obligations` — pas encore une ligne en base. `agents/` ne touche
    jamais la DB (voir séparation agents/ vs backend/<acteur>/services/),
    donc cette forme est ce que l'agent retourne au service pour que lui
    l'écrive.
    """
    nom: str
    description: str
    legal_text_id: UUID | None = None
    lie_a_aipd: bool = False
