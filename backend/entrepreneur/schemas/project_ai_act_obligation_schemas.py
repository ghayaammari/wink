"""Schémas Pydantic pour `project_ai_act_obligations` — service 3.3.12 (AI

Act). Copie conforme de `project_rgpd_obligation_schemas.py`, sans le champ
`lie_a_aipd` (pas d'équivalent AI Act, voir docstring du modèle)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from backend.entrepreneur.schemas.project_ai_act_classification_schemas import (
    ProjectAiActClassificationRead,
)

ObligationStatut = Literal["a_faire", "fait"]


class ProjectAiActObligationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    nom: str
    description: str
    statut: ObligationStatut
    legal_text_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectAiActObligationStatutUpdate(BaseModel):
    statut: ObligationStatut


class AiActObligationCandidate(BaseModel):
    """Une obligation proposée par l'agent AI Act, avant passage dans

    `sync_obligations` — pas encore une ligne en base (même principe que
    `RgpdObligationCandidate`, voir project_rgpd_obligation_schemas.py)."""
    nom: str
    description: str
    legal_text_id: UUID | None = None


class AiActDiagnosticRunResult(BaseModel):
    """Réponse du POST /projects/{id}/ai-act/diagnostic : classification ET

    obligations en un seul retour, pour éviter un second aller-retour
    frontend juste après le déclenchement du diagnostic (voir
    ai_act_router.py)."""
    classification: ProjectAiActClassificationRead
    obligations: list[ProjectAiActObligationRead]
