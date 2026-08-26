"""Schémas Pydantic pour l'authentification — partagés par les 3 acteurs (I0).

Un seul fichier ici, contrairement à `entrepreneur/schemas/` où c'est un fichier
par table : la responsabilité de ce module n'est pas "représenter la table
`users`", c'est "représenter les échanges des 5 endpoints d'auth" (signup,
login, session) — un flux, pas une table.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["entrepreneur", "chercheur", "investisseur"]


class SignupRequest(BaseModel):
    """Écran 1 du questionnaire — création de compte par email/mot de passe.

    first_name/last_name sont obligatoires ici alors que la colonne `users`
    les autorise NULL : la nullabilité en base sert le provider Google (rempli
    automatiquement par Google, jamais demandé à l'utilisateur) ; ici, côté
    email, rien ne les remplit automatiquement donc le schéma les impose pour
    ne pas se retrouver avec des comptes sans nom.
    """

    email: EmailStr
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    # min_length=8 : évite qu'un mot de passe vide/trivial atteigne le hash bcrypt
    # et finisse en base — le cas limite classique découvert seulement à la reconnexion.
    password: str = Field(min_length=8)
    role: Role


class GoogleSignupRequest(BaseModel):
    """Écran 1 — bouton "Continuer avec Google". Pas de mot de passe : ce chemin

    ne remplit jamais `password_hash`. Réutilisé tel quel pour la connexion
    Google (POST /auth/login/google) — le service décide en interne si c'est
    une création ou une connexion selon que `provider_subject` existe déjà.
    """

    id_token: str  # jeton brut du SDK Google côté frontend, vérifié par le service
    role: Role


class LoginRequest(BaseModel):
    """Connexion classique par email/mot de passe."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Réponse renvoyée après un signup/login/refresh réussi (email ou Google)."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RefreshRequest(BaseModel):
    """POST /auth/refresh — échange un refresh token encore valide contre une nouvelle paire."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password — déclenche l'envoi du lien de réinitialisation."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password — le lien reçu par email pointe vers un écran

    frontend qui collecte le nouveau mot de passe et renvoie ces deux champs.
    """

    token: str
    new_password: str = Field(min_length=8)


class UserRead(BaseModel):
    """Réponse de GET /auth/me — volontairement sans `password_hash` ni

    `provider_subject` : ce sont des colonnes internes du modèle SQLAlchemy
    `User`, jamais exposées par l'API.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    role: Role
    created_at: datetime
