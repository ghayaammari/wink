"""Schémas Pydantic pour `healthtech_data_profile` — service 3.3.5 (HealthTech).

Même mécanisme tri-état que `ai_act_data_profile_schemas.py` : `bool | None`,
`None` = pas encore répondu, PATCH via `exclude_unset=True` côté service. Les
`description` sont le texte exact des questions posées à l'entrepreneur sur
la carte "Conformité sectorielle > HealthTech".
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HealthtechDataProfileUpdate(BaseModel):
    est_dispositif_medical: bool | None = Field(
        default=None,
        description=(
            "Votre produit est-il un dispositif médical au sens réglementaire (destiné au "
            "diagnostic, à la prévention, au contrôle ou au traitement d'une maladie, d'une "
            "blessure ou d'un handicap) ?"
        ),
    )
    fournit_aide_decision_diagnostique_ou_therapeutique: bool | None = Field(
        default=None,
        description=(
            "Votre produit fournit-il une aide à la décision diagnostique ou thérapeutique "
            "(il analyse des données de santé pour orienter un diagnostic ou un traitement) ?"
        ),
    )
    risque_deces_ou_deterioration_irreversible: bool | None = Field(
        default=None,
        description=(
            "Une erreur de votre produit peut-elle entraîner un décès ou une détérioration "
            "irréversible de l'état de santé du patient ?"
        ),
    )
    risque_intervention_chirurgicale_ou_deterioration_grave: bool | None = Field(
        default=None,
        description=(
            "Une erreur de votre produit peut-elle nécessiter une intervention chirurgicale "
            "ou entraîner une détérioration grave de l'état de santé du patient ?"
        ),
    )


class HealthtechDataProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    est_dispositif_medical: bool | None
    fournit_aide_decision_diagnostique_ou_therapeutique: bool | None
    risque_deces_ou_deterioration_irreversible: bool | None
    risque_intervention_chirurgicale_ou_deterioration_grave: bool | None
    created_at: datetime
    updated_at: datetime
