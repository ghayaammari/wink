"""Modèle — investor_profiles. Parcours linéaire (pas de branchement comme
chercheur/entrepreneur) : une seule table à remplir, voir
investor_table___questions__1_.pdf.

organization_name : ajouté suite au point ouvert du PDF — présence =
l'investisseur représente une organisation/un fonds, absence = investit à
titre personnel. Pas de colonne booléenne séparée, la présence du champ
suffit à distinguer les deux cas.

investor_type : ajouté le 06/09/2026 — obligatoire à l'onboarding (contrainte
appliquée côté schéma Pydantic, colonne nullable en base), valeur unique
parmi vc/business_angel/family_office/corporate_vc/fonds_public/autre.
Compte désormais dans profile_completion.

profile_completion : "0%"/"33%"/"67%"/"100%" (4 paliers, un par champ compté
sur 3 : investor_type, investment_thesis, contact_email) — organization_name
ne compte toujours pas dans ce calcul (précision facultative, pas utile au
matching/contact)."""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.shared.database import Base


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"
    __table_args__ = (
        CheckConstraint("profile_completion IN ('0%', '33%', '67%', '100%')", name="ck_investor_profiles_completion"),
        CheckConstraint(
            "investor_type IN ('vc', 'business_angel', 'family_office', 'corporate_vc', 'fonds_public', 'autre')",
            name="ck_investor_profiles_investor_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    organization_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    investor_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    investment_thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    profile_completion: Mapped[str] = mapped_column(String(20), nullable=False, server_default="0%")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)