"""Réexporte toutes les tables communes — obligatoire pour qu'Alembic les détecte."""
from backend.shared.models.password_reset_token import PasswordResetToken
from backend.shared.models.refresh_token import RefreshToken
from backend.shared.models.user import User

__all__ = ["PasswordResetToken", "RefreshToken", "User"]
