"""Schémas Pydantic pour `compliance_data_profile` — service 3.3.1 (RGPD).

Diagnostic tri-état : chaque champ est `bool | None`, où `None` signifie "pas
encore répondu" (distinct de `False`, voir docstring du modèle). Le PATCH
s'appuie sur `exclude_unset=True` côté service (même mécanisme que
`update_legal_profile` dans project_service.py) pour ne modifier que les
champs réellement envoyés par le client — sinon un client qui omet un champ
dans son payload l'écraserait silencieusement à `None`.

Les `description` ci-dessous sont le texte exact des questions posées à
l'entrepreneur à la première visite de la carte RGPD — portées par le schéma
(et non un doc séparé, absent de l'architecture) pour rester versionnées avec
le champ qu'elles renseignent. Ce sont aussi ces réponses qui pilotent
directement quelles obligations sont générées (voir
backend/entrepreneur/services/rgpd_diagnostic_service.py) : changer une
réponse ici change le résultat du diagnostic, ce n'est jamais une liste
statique.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ComplianceDataProfileUpdate(BaseModel):
    collecte_donnees_sensibles: bool | None = Field(
        default=None,
        description=(
            "Votre projet collecte-t-il des données personnelles sensibles au sens du RGPD "
            "(santé, origine raciale ou ethnique, opinions politiques ou religieuses, "
            "appartenance syndicale, vie sexuelle ou orientation sexuelle, données "
            "biométriques ou génétiques) ?"
        ),
    )
    collecte_donnees_mineurs: bool | None = Field(
        default=None,
        description=(
            "Votre service est-il proposé directement à des mineurs de moins de 15 ans "
            "(ex : application ou plateforme accessible à des enfants ou adolescents) ?"
        ),
    )
    profilage: bool | None = Field(
        default=None,
        description=(
            "Votre projet réalise-t-il un profilage automatisé de vos utilisateurs "
            "(scoring, recommandation personnalisée, décision automatisée les concernant) ?"
        ),
    )
    partage_avec_tiers: bool | None = Field(
        default=None,
        description=(
            "Faites-vous appel à des prestataires qui traitent des données pour votre compte "
            "(hébergeur, outil d'emailing, paiement, analytics...), ou partagez-vous des "
            "données personnelles avec des partenaires externes ?"
        ),
    )
    transfert_hors_ue: bool | None = Field(
        default=None,
        description=(
            "Une partie de ces données est-elle hébergée ou traitée en dehors de l'Union "
            "européenne (ex : prestataire américain, hébergement cloud hors UE) ?"
        ),
    )


class ComplianceDataProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    collecte_donnees_sensibles: bool | None
    collecte_donnees_mineurs: bool | None
    profilage: bool | None
    partage_avec_tiers: bool | None
    transfert_hors_ue: bool | None
    created_at: datetime
    updated_at: datetime
