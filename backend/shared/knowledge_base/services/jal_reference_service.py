"""Persistance de `jal_reference` (service 1.1.5) — lecture/écriture DB
uniquement. Ne commit jamais : à l'appelant de décider quand committer."""
import uuid
from datetime import date

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.jal_reference import JalReference


class JalReferenceNotFoundError(Exception):
    """Aucune ligne `jal_reference` avec cet id."""


def upsert_jal(
    db: Session,
    *,
    nom_journal: str,
    type_support: str,
    departements_couverts: list[str],
    lien_site: str | None,
    source_url: str,
) -> tuple[JalReference, bool]:
    """Insère ou met à jour par `source_url` (fiche du journal sur la source).
    Un journal retrouvé redevient `actif`. Repasse en `extrait_automatique`
    si le contenu a changé (ex. départements différents d'une année à l'autre)."""
    existant = db.query(JalReference).filter(JalReference.source_url == source_url).first()
    valeurs = dict(
        nom_journal=nom_journal,
        departements_couverts=sorted(departements_couverts),
        lien_site=lien_site,
        source_url=source_url,
    )
    if existant is not None:
        a_change = any(getattr(existant, k) != v for k, v in valeurs.items())
        for k, v in valeurs.items():
            setattr(existant, k, v)
        # type_support n'est pas écrasé : il a pu être corrigé à la validation humaine.
        existant.actif = True
        if a_change:
            existant.statut_contenu = "extrait_automatique"
        db.flush()
        return existant, False
    ligne = JalReference(type_support=type_support, **valeurs)
    db.add(ligne)
    db.flush()
    return ligne, True


def desactiver_absents(db: Session, source_urls_vues: set[str]) -> int:
    """Journaux absents de la dernière collecte COMPLÈTE -> `actif=False`
    (habilitation non renouvelée). Jamais supprimés : historique conservé."""
    absents = (
        db.query(JalReference)
        .filter(JalReference.actif.is_(True), JalReference.source_url.notin_(source_urls_vues))
        .all()
    )
    for ligne in absents:
        ligne.actif = False
    db.flush()
    return len(absents)


def list_pending_validation(db: Session) -> list[JalReference]:
    return (
        db.query(JalReference)
        .filter(JalReference.statut_contenu == "extrait_automatique", JalReference.actif.is_(True))
        .order_by(JalReference.nom_journal)
        .all()
    )


def validate_jal(db: Session, jal_id: uuid.UUID, type_support: str | None = None) -> JalReference:
    """Passe en `valide_humain` ; `type_support` corrige l'heuristique si fourni.
    Ne commit jamais."""
    ligne = db.get(JalReference, jal_id)
    if ligne is None:
        raise JalReferenceNotFoundError(f"jal_reference.id={jal_id} introuvable.")
    if type_support is not None:
        ligne.type_support = type_support
    ligne.statut_contenu = "valide_humain"
    ligne.derniere_verification = date.today()
    db.flush()
    return ligne
