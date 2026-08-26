"""Table `refresh_tokens` — sessions de rafraîchissement, revocables, hors schéma I0 initial.

Ajoutée pour supporter le refresh token demandé en plus des 5 endpoints d'auth
déjà actés dans l'architecture. Placée dans `shared/models/` (comme `user.py`)
et non sous `shared/auth/` : l'architecture ne définit pas de `auth/models/`,
et cette table est aussi centrale à l'identité que `users` — pas spécifique
à un sous-module d'auth.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Jamais le token en clair : un leak de la table ne doit pas donner des sessions valides.
    # SHA-256 suffit (pas bcrypt) — le token est déjà 64 octets aléatoires, pas un mot de
    # passe humain à ralentir contre le brute-force.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = encore valide. Posé à la date d'utilisation lors de la rotation, ou au logout.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
