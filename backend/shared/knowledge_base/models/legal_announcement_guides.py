"""Table `legal_announcement_guides` — pages de guides pratiques officiels sur
l'annonce légale (Service-Public, economie.gouv.fr, Bpifrance Création…),
pour le copilot (service 1.1.5) : délais, prix, contenu, attestation, où
publier.

Table dédiée (décision utilisateur, 25/09/2026) plutôt que `legal_texts` :
`legal_texts` = articles de loi (clé `(code_source, article_numero)`) ; une
page de guide n'a pas de numéro d'article. Les articles R210-3/R210-4/R210-16
vont, eux, dans `legal_texts` (domaine `annonce_legale`).
NB : le pipeline du pacte (1.1.13) avait rangé des pages Bpifrance dans
`legal_texts` (titre de page en `article_numero`) — précédent non repris ici.

`texte_brut` ne provient QUE d'un vrai `fetch_page()` (jamais rédigé à la main
ni par un LLM). Insertion en `extrait_automatique` ; seules les lignes
`valide_humain` sont chunkées/embeddées (`chunk_and_embed_legal_announcement_guides.py`,
domaine `annonce_legale`).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class LegalAnnouncementGuide(Base):
    __tablename__ = "legal_announcement_guides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_nom: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    titre: Mapped[str] = mapped_column(Text, nullable=False)
    # Sujet principal, fixé à la curation de l'URL (jamais deviné par un LLM) :
    # 'obligation_contenu' | 'tarif' | 'choix_journal' | 'attestation' | 'general'.
    sous_theme: Mapped[str] = mapped_column(String(50), nullable=False)
    texte_brut: Mapped[str] = mapped_column(Text, nullable=False)
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    derniere_verification: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_url", name="uq_legal_announcement_guides_source_url"),
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_legal_announcement_guides_statut_contenu",
        ),
    )
