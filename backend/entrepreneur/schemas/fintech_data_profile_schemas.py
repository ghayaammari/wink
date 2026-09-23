"""Schémas Pydantic pour `fintech_data_profile` — service 3.3.5 (FinTech).

Même mécanisme tri-état que `ai_act_data_profile_schemas.py` : `bool | None`,
`None` = pas encore répondu, PATCH via `exclude_unset=True` côté service. Les
`description` sont le texte exact des questions posées à l'entrepreneur sur
la carte "Conformité sectorielle > FinTech".
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FintechDataProfileUpdate(BaseModel):
    gere_fonds_ou_paiements_clients: bool | None = Field(
        default=None,
        description=(
            "Votre projet détient-il, gère-t-il ou transmet-il des fonds ou des paiements "
            "pour le compte de vos clients ?"
        ),
    )
    volume_mensuel_depasse_3_millions: bool | None = Field(
        default=None,
        description="Le volume mensuel des paiements traités dépasse-t-il 3 millions d'euros ?",
    )
    propose_transmission_de_fonds: bool | None = Field(
        default=None,
        description=(
            "Proposez-vous un service de transmission de fonds (envoi d'argent entre "
            "particuliers ou entreprises, sans tenir de compte de paiement) ?"
        ),
    )
    gere_investissement_ou_actifs: bool | None = Field(
        default=None,
        description=(
            "Votre projet gère-t-il de l'investissement ou des actifs pour le compte de vos "
            "clients (conseil en investissement, gestion de portefeuille, actifs numériques) ?"
        ),
    )


class FintechDataProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    gere_fonds_ou_paiements_clients: bool | None
    volume_mensuel_depasse_3_millions: bool | None
    propose_transmission_de_fonds: bool | None
    gere_investissement_ou_actifs: bool | None
    created_at: datetime
    updated_at: datetime
