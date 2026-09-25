"""Persistance de `administrative_guides` — pas de logique de scraping/LLM ici,
uniquement lecture/ecriture DB. Meme separation que `legal_texts_service.py` :
le texte brut vient de `scrapers/shared/web_fetch.py`, aucune classification
LLM n'intervient (voir modele, `domaine` est fixe par la source).

Ne commit jamais la session : a l'appelant de decider (voir
`collect_administrative_guides.py` et `administrative_guides_validation_router.py`).
"""
import uuid

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.administrative_guides import AdministrativeGuide


class AdministrativeGuideNotFoundError(Exception):
    """Aucune ligne `administrative_guides` avec cet id."""


def upsert_administrative_guide(
    db: Session,
    *,
    domaine: str,
    source_nom: str,
    source_url: str,
    texte_brut: str,
    titre: str | None = None,
) -> tuple[AdministrativeGuide, bool]:
    """Insere ou met a jour la ligne identifiee par (domaine, source_url).

    `statut_contenu` n'est jamais un parametre : toujours 'extrait_automatique'
    a l'insertion, et repasse en 'extrait_automatique' UNIQUEMENT si le texte a
    reellement change sur une mise a jour — meme garde-fou que
    `upsert_legal_text` (une validation humaine faite sur l'ancien texte ne
    garantit rien sur le nouveau).
    """
    existing = (
        db.query(AdministrativeGuide)
        .filter(AdministrativeGuide.domaine == domaine, AdministrativeGuide.source_url == source_url)
        .first()
    )
    if existing is not None:
        content_changed = existing.texte_brut != texte_brut or existing.titre != titre
        existing.texte_brut = texte_brut
        existing.titre = titre
        existing.source_nom = source_nom
        if content_changed:
            existing.statut_contenu = "extrait_automatique"
        db.flush()
        return existing, False

    row = AdministrativeGuide(
        domaine=domaine,
        source_nom=source_nom,
        source_url=source_url,
        texte_brut=texte_brut,
        titre=titre,
    )
    db.add(row)
    db.flush()
    return row, True


def list_valide_humain(db: Session) -> list[AdministrativeGuide]:
    """Lignes deja relues et confirmees — seules celles-ci sont chunkees/
    embeddees, voir `chunk_and_embed_administrative_guides.py`."""
    return (
        db.query(AdministrativeGuide)
        .filter(AdministrativeGuide.statut_contenu == "valide_humain")
        .order_by(AdministrativeGuide.collecte_le)
        .all()
    )


def list_pending_validation(db: Session) -> list[AdministrativeGuide]:
    """Lignes en attente de relecture humaine, triees par ordre de collecte."""
    return (
        db.query(AdministrativeGuide)
        .filter(AdministrativeGuide.statut_contenu == "extrait_automatique")
        .order_by(AdministrativeGuide.collecte_le)
        .all()
    )


def validate_administrative_guide(db: Session, guide_id: uuid.UUID) -> AdministrativeGuide:
    """Passe la ligne en 'valide_humain'. Pas d'action 'corriger' ici
    (contrairement a `legal_texts`) : il n'y a pas de choix de decoupage a
    inverser, le contenu est toujours des paragraphes de prose (voir
    `chunk_and_embed_administrative_guides.py`, chunk_texte_guide()).
    Ne commit jamais (au routeur de committer)."""
    row = db.query(AdministrativeGuide).filter(AdministrativeGuide.id == guide_id).first()
    if row is None:
        raise AdministrativeGuideNotFoundError(f"administrative_guides.id={guide_id} introuvable.")
    row.statut_contenu = "valide_humain"
    db.flush()
    return row
