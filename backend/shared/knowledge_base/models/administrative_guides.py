"""Table `administrative_guides` — corpus de guides web non-legaux pour les
domaines administratifs de l'Increment 1 qui n'ont pas de source Legifrance
(ex: pacte_fondateurs, pre_depot). Generique par construction (contrairement
a `legal_texts`, propre aux articles de loi, et a
`sector_insurance_recommendations`, propre a la classification par type
d'assurance) : sert n'importe quel domaine scrape en page web, un
`domaine` en plus dans la CheckConstraint suffit a en ajouter un nouveau.

Alimentee par `backend/shared/knowledge_base/scripts/
collect_administrative_guides.py` — jamais saisie a la main. Toute ligne
inseree l'est en `statut_contenu='extrait_automatique'` (jamais directement
en `valide_humain`) : meme principe de relecture humaine obligatoire avant
usage par un agent que pour `legal_texts`/`sector_insurance_recommendations`
(voir `administrative_guides_validation_router.py`).

Pas de classification LLM a la collecte (contrairement au volet assurance) :
le `domaine` est fixe par la source (voir `scrapers/<source>/pages_*.py`),
jamais devine par un LLM — meme principe que `forme_juridique_concernee` sur
`legal_texts`. Ca evite un appel Groq inutile pour un decoupage deja connu a
l'avance, ce qui compte vu le quota (8000 TPM/organisation, voir
`chercheur_matching_tools_service.py`).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class AdministrativeGuide(Base):
    __tablename__ = "administrative_guides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Liste fermee, voir CheckConstraint ci-dessous — meme valeurs que
    # `content_embeddings.domaine` (deja reservees par la migration
    # 6f1a2c9d3e5b) pour ces 2 domaines.
    domaine: Mapped[str] = mapped_column(String(50), nullable=False)
    source_nom: Mapped[str] = mapped_column(String(150), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    titre: Mapped[str | None] = mapped_column(String(255), nullable=True)
    texte_brut: Mapped[str] = mapped_column(Text, nullable=False)
    chunking_suggere: Mapped[str] = mapped_column(String(20), nullable=False, server_default="par_paragraphe")
    statut_contenu: Mapped[str] = mapped_column(String(20), nullable=False, server_default="extrait_automatique")
    collecte_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        # (domaine, source_url) et non source_url seul : la meme URL ne peut
        # pas exister deux fois avec des domaines differents, mais protege
        # aussi contre une source_url dupliquee au sein d'un meme domaine.
        UniqueConstraint("domaine", "source_url", name="uq_administrative_guides_domaine_url"),
        CheckConstraint(
            "statut_contenu IN ('extrait_automatique', 'valide_humain')",
            name="ck_administrative_guides_statut_contenu",
        ),
        CheckConstraint(
            "domaine IN ('pacte_fondateurs', 'pre_depot', 'statuts', 'tarifs', 'annonce_legale')",
            name="ck_administrative_guides_domaine",
        ),
    )
