"""Schémas Pydantic pour `project_certification_obligations` — service 3.3.11.

Même principe que project_rgpd_obligation_schemas.py : seul "statut" est
settable par le client (case à cocher) -- nom/description/ordre/legal_text_id
ne seront écrits que par la future génération (compliance_agent), pas encore
construite (voir docstring du service).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ObligationStatut = Literal["a_faire", "fait"]
# V1 limitée à SecNumCloud (voir migration q4d6f8a0b2c4) -- ISO 27001/SOC 2
# s'ajouteront ici en même temps que sur la CheckConstraint DB.
TypeCertification = Literal["secnumcloud"]


class ProjectCertificationObligationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type_certification: TypeCertification
    nom: str
    description: str
    ordre: int
    statut: ObligationStatut
    legal_text_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectCertificationObligationStatutUpdate(BaseModel):
    statut: ObligationStatut


class CertificationObligationCandidate(BaseModel):
    """Sortie intermédiaire entre l'agent (CertificationObligationCandidate

    côté agents/, avec un source_id brut) et sync_obligations : legal_text_id
    déjà résolu par l'orchestrateur (secnumcloud_diagnostic_service.py), même
    principe que RgpdObligationCandidate.
    """

    nom: str
    description: str
    ordre: int
    legal_text_id: UUID | None
