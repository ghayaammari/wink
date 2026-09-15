"""Persistance de `sector_insurance_recommendations` — pas de logique IA/API
externe ici, uniquement de la lecture/ecriture DB. Meme separation que
`legal_texts_service.py` : classification dans
`agents/ingestion/sector_insurance_structuring_service.py`, persistance ici.

Ne commit jamais la session : a l'appelant de decider quand committer.
"""
import uuid

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.sector_insurance_recommendations import SectorInsuranceRecommendation


class SectorInsuranceNotFoundError(Exception):
    """Aucune ligne `sector_insurance_recommendations` avec cet id."""


def upsert_sector_insurance(
    db: Session,
    *,
    secteurs: list[str],
    type_assurance: str,
    a_base_legale: bool = False,
    legal_text_id: uuid.UUID | None = None,
    source_nom: str | None = None,
    source_url: str | None = None,
    texte_brut: str | None = None,
) -> tuple[SectorInsuranceRecommendation, bool]:
    """Insere ou met a jour.

    Cle de recherche (correctif du 11/09/2026 — `secteur` devient `secteurs`,
    liste, voir plan de correction) :
    - si `legal_text_id` est fourni (volet base legale) : cherche par
      `legal_text_id` seul. 1 article = 1 ligne, tous ses secteurs dans le
      meme tableau — `legal_text_id` est deja unique en base (voir
      UniqueConstraint sur le modele), pas besoin de `secteurs` dans la cle.
    - sinon (volet non-legal) : cherche par `(type_assurance, source_url)` —
      volontairement pas `secteurs` dans la cle (egalite sur un array
      fragile), cle PROVISOIRE si la conception du volet 2 evolue encore.
      `collect_sector_insurance_pages.py` regroupe deja les secteurs
      pertinents PAR `type_assurance` avant d'appeler cette fonction (une
      meme page est souvent pertinente pour plusieurs secteurs a la fois) :
      un seul appel par (page, type_assurance), jamais un appel par secteur
      — cette fonction REMPLACE `secteurs`, elle ne fusionne pas avec les
      secteurs deja stockes.

    Retourne (ligne, was_created). Meme garde-fou que `upsert_legal_text` :
    repasse en 'extrait_automatique' si le contenu a reellement change.
    """
    if legal_text_id is not None:
        existing = (
            db.query(SectorInsuranceRecommendation)
            .filter(SectorInsuranceRecommendation.legal_text_id == legal_text_id)
            .first()
        )
    else:
        existing = (
            db.query(SectorInsuranceRecommendation)
            .filter(
                SectorInsuranceRecommendation.type_assurance == type_assurance,
                SectorInsuranceRecommendation.source_url == source_url,
            )
            .first()
        )

    values = dict(
        secteurs=secteurs,
        type_assurance=type_assurance,
        a_base_legale=a_base_legale,
        legal_text_id=legal_text_id,
        source_nom=source_nom,
        source_url=source_url,
        texte_brut=texte_brut,
    )
    if existing is not None:
        content_changed = any(getattr(existing, k) != v for k, v in values.items())
        for k, v in values.items():
            setattr(existing, k, v)
        if content_changed:
            existing.statut_contenu = "extrait_automatique"
        db.flush()
        return existing, False

    row = SectorInsuranceRecommendation(**values)
    db.add(row)
    db.flush()
    return row, True


def list_valide_humain(db: Session) -> list[SectorInsuranceRecommendation]:
    """Lignes relues et confirmees — seules celles-ci sont chunkees/embeddees."""
    return (
        db.query(SectorInsuranceRecommendation)
        .filter(SectorInsuranceRecommendation.statut_contenu == "valide_humain")
        .order_by(SectorInsuranceRecommendation.collecte_le)
        .all()
    )


def list_pending_validation(db: Session) -> list[SectorInsuranceRecommendation]:
    """Lignes en attente de relecture humaine."""
    return (
        db.query(SectorInsuranceRecommendation)
        .filter(SectorInsuranceRecommendation.statut_contenu == "extrait_automatique")
        .order_by(SectorInsuranceRecommendation.collecte_le)
        .all()
    )


def validate_sector_insurance(
    db: Session, record_id: uuid.UUID, action: str
) -> SectorInsuranceRecommendation:
    """'valider' passe en valide_humain ; 'corriger' passe en valide_humain ET
    inverse `a_base_legale` (seule correction que ce dashboard permet).
    Ne commit jamais.
    """
    row = (
        db.query(SectorInsuranceRecommendation)
        .filter(SectorInsuranceRecommendation.id == record_id)
        .first()
    )
    if row is None:
        raise SectorInsuranceNotFoundError(
            f"sector_insurance_recommendations.id={record_id} introuvable."
        )
    row.statut_contenu = "valide_humain"
    if action == "corriger":
        row.a_base_legale = not row.a_base_legale
    db.flush()
    return row
