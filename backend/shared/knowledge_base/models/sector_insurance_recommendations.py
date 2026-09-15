"""Table `sector_insurance_recommendations` — recommandations d'assurance par
secteur, avec ou sans base legale (Groupe 2, service 1.1.10).

Une ligne = un type d'assurance, avec la liste des secteurs concernes (ex:
"RC Pro" pour ["FinTech", "SaaS / Tech generique", ...]), avec indication de
la source : soit un article de loi (`a_base_legale=true`, `legal_text_id`
pointe vers `legal_texts`), soit un guide professionnel (`a_base_legale=false`,
`source_nom`/`source_url`/`texte_brut`).

CORRECTIF du 11/09/2026 : `secteurs` etait `secteur` (scalaire) — 1 ligne par
(article, secteur), jusqu'a 11 lignes identiques pour le meme article. Passe
en array (meme principe que `legal_texts.forme_juridique_concernee`) : 1
ligne par article, tous ses secteurs dans le meme tableau. Corrige un vrai
risque de desynchronisation en validation humaine (11 cartes identiques pour
le meme article, validables independamment — voir discussion du 11/09/2026).

Alimentee par `backend/shared/knowledge_base/scripts/
collect_sector_insurance_recommendations.py` — jamais saisie a la main.
Toute ligne inseree l'est en `statut_contenu='extrait_automatique'` ; la
validation humaine passe par le dashboard dedie (meme principe que
`legal_texts` / `LegalTextsValidationPage`).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class SectorInsuranceRecommendation(Base):
    __tablename__ = "sector_insurance_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    secteurs: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )
    type_assurance: Mapped[str] = mapped_column(String(120), nullable=False)
    a_base_legale: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    legal_text_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_texts.id"), nullable=True
    )
    source_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    texte_brut: Mapped[str | None] = mapped_column(Text, nullable=True)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_sector_insurance_statut_contenu",
        ),
        # 1 ligne par article (secteurs en array) : legal_text_id seul suffit
        # comme cle unique. NULL n'est jamais egal a NULL en SQL, donc cette
        # contrainte ne s'applique qu'aux lignes du volet base legale
        # (legal_text_id non nul) ; le volet non-legal n'est pas couvert.
        UniqueConstraint("legal_text_id", name="uq_sector_insurance_legal_text"),
    )
