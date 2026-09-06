"""Schémas Pydantic — investor_profiles. Parcours linéaire (pas de
branchement comme chercheur/entrepreneur) : un seul schéma d'onboarding
couvrant type d'investisseur + organisation + thèse + email de contact,
envoyé en un seul appel (même décision que POST /chercheur/onboarding —
onboarding court, rien à reprendre à mi-chemin).

investor_type : obligatoire à l'onboarding (contrainte appliquée ici, pas en
base — colonne nullable pour ne jamais bloquer une migration sur des lignes
existantes). Valeur unique, pas de multi-sélection (décision actée le
06/09/2026)."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

InvestorType = Literal["vc", "business_angel", "family_office", "corporate_vc", "fonds_public", "autre"]


class InvestorOnboardingRequest(BaseModel):
    investor_type: InvestorType
    organization_name: str | None = Field(default=None, max_length=255)
    investment_thesis: str | None = None
    contact_email: EmailStr | None = None

    @model_validator(mode="after")
    def _at_least_one_optional_field(self) -> "InvestorOnboardingRequest":
        # Décision actée : en plus de investor_type (toujours obligatoire),
        # l'onboarding exige au moins un des deux champs restants (thèse ou
        # email de contact) — organization_name ne compte pas, il n'alimente
        # pas le matching, contrairement aux deux autres.
        if not self.investment_thesis and not self.contact_email:
            raise ValueError("investment_thesis ou contact_email requis pour compléter l'onboarding.")
        return self


class InvestorProfileUpdate(BaseModel):
    """Modification libre après l'onboarding (service 0.0.3) — tous
    optionnels, aucune contrainte de "au moins un champ" ici contrairement à
    l'onboarding : un investisseur peut très bien tout vider après coup, le
    gate ne se revérifie qu'à l'entrée dans le dashboard, pas en continu
    (voir dette technique assumée : rejoue l'onboarding si tout est vidé
    puis qu'il se reconnecte)."""

    investor_type: InvestorType | None = None
    organization_name: str | None = Field(default=None, max_length=255)
    investment_thesis: str | None = None
    contact_email: EmailStr | None = None


class InvestorProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    organization_name: str | None
    investor_type: InvestorType | None
    investment_thesis: str | None
    contact_email: str | None
    profile_completion: Literal["0%", "33%", "67%", "100%"]
    created_at: datetime
    updated_at: datetime