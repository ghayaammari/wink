"""Table `users` — compte applicatif, commun aux 3 rôles (entrepreneur, chercheur, investisseur)."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, server_default="email")
    provider_subject: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("role IN ('entrepreneur', 'chercheur', 'investisseur')", name="ck_users_role"),
        CheckConstraint("auth_provider IN ('email', 'google')", name="ck_users_auth_provider"),
        CheckConstraint(
            "auth_provider <> 'email' OR password_hash IS NOT NULL",
            name="ck_users_password_hash_required_for_email",
        ),
        CheckConstraint(
            "auth_provider <> 'google' OR provider_subject IS NOT NULL",
            name="ck_users_provider_subject_required_for_google",
        ),
        # Index unique sur lower(email) — insensible à la casse, en plus de l'UNIQUE brut sur email.
        Index("ix_users_email_lower", text("lower(email)"), unique=True),
    )
