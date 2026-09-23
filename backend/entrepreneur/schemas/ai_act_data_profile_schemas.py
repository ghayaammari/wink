"""Schémas Pydantic pour `ai_act_data_profile` — service 3.3.12 (AI Act).

Même mécanisme tri-état que `compliance_data_profile_schemas.py` (RGPD) :
`bool | None`, `None` = pas encore répondu, PATCH via `exclude_unset=True`
côté service. Les `description` sont le texte exact des questions posées à
l'entrepreneur sur la carte "Conformité > AI Act".
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AiActDataProfileUpdate(BaseModel):
    utilise_ia: bool | None = Field(
        default=None,
        description=(
            "Votre projet utilise-t-il un système d'intelligence artificielle dans son "
            "fonctionnement (au sens du règlement européen sur l'IA — modèle de machine "
            "learning, LLM, système de recommandation automatisé...) ?"
        ),
    )
    usage_biometrie_ou_identification: bool | None = Field(
        default=None,
        description=(
            "Votre système réalise-t-il de l'identification biométrique à distance ou de la "
            "catégorisation biométrique de personnes (reconnaissance faciale, analyse "
            "d'émotions, catégorisation par caractéristiques physiques) ?"
        ),
    )
    usage_scoring_emploi_credit_ou_education: bool | None = Field(
        default=None,
        description=(
            "Votre système est-il utilisé pour évaluer, sélectionner ou noter des personnes "
            "dans un contexte de recrutement/emploi, d'octroi de crédit, ou d'éducation/examens ?"
        ),
    )
    usage_infrastructure_ou_securite_critique: bool | None = Field(
        default=None,
        description=(
            "Votre système est-il utilisé pour gérer ou sécuriser une infrastructure critique "
            "(énergie, eau, transport...) ou un dispositif de sécurité ?"
        ),
    )
    interagit_ou_genere_contenu_pour_utilisateurs: bool | None = Field(
        default=None,
        description=(
            "Votre système interagit-il directement avec les utilisateurs (chatbot, assistant "
            "conversationnel) ou génère-t-il du contenu (texte, image, audio, vidéo) qui leur "
            "est présenté ?"
        ),
    )
    developpe_modele_ia_usage_general: bool | None = Field(
        default=None,
        description=(
            "Développez-vous vous-même un modèle d'IA à usage général/de fondation (par "
            "opposition à l'utilisation d'une API tierce existante comme OpenAI, Groq...) ?"
        ),
    )


class AiActDataProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    utilise_ia: bool | None
    usage_biometrie_ou_identification: bool | None
    usage_scoring_emploi_credit_ou_education: bool | None
    usage_infrastructure_ou_securite_critique: bool | None
    interagit_ou_genere_contenu_pour_utilisateurs: bool | None
    developpe_modele_ia_usage_general: bool | None
    created_at: datetime
    updated_at: datetime
