"""Table `password_reset_tokens` — jetons de réinitialisation de mot de passe, hors schéma I0 initial.

Même raisonnement de placement que `refresh_token.py` : pas de `auth/models/`
dans l'architecture, table centrale à l'identité, placée dans `shared/models/`.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Même logique que refresh_tokens : jamais le token en clair, SHA-256 suffit
    # (déjà 64 octets aléatoires, pas un mot de passe humain).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # Durée de vie volontairement courte (config ACCESS... non, voir
    # PASSWORD_RESET_TOKEN_EXPIRE_MINUTES dans auth_service.py) : un lien de
    # reset qui traîne des jours dans une boîte mail est un risque, contrairement
    # au refresh token pensé pour durer.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = encore utilisable. Posé à la date d'utilisation — usage unique, comme
    # la rotation des refresh tokens.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
