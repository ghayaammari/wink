"""Persistance de `legal_announcement_guides` (service 1.1.5, copilot) —
lecture/écriture DB uniquement, aucun appel réseau ni LLM. Ne commit jamais :
à l'appelant de décider quand committer.
"""
import uuid

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.legal_announcement_guides import LegalAnnouncementGuide


class LegalAnnouncementGuideNotFoundError(Exception):
    """Aucune ligne `legal_announcement_guides` avec cet id."""


def upsert_guide(
    db: Session, *, source_nom: str, source_url: str, titre: str, sous_theme: str, texte_brut: str
) -> tuple[LegalAnnouncementGuide, bool]:
    """Insère ou met à jour par `source_url`. Repasse en `extrait_automatique`
    si le contenu a réellement changé (une validation faite sur l'ancien
    texte ne garantit rien sur le nouveau — même règle que `upsert_legal_text`)."""
    existant = db.query(LegalAnnouncementGuide).filter(LegalAnnouncementGuide.source_url == source_url).first()
    valeurs = dict(source_nom=source_nom, source_url=source_url, titre=titre, sous_theme=sous_theme, texte_brut=texte_brut)
    if existant is not None:
        a_change = any(getattr(existant, k) != v for k, v in valeurs.items())
        for k, v in valeurs.items():
            setattr(existant, k, v)
        if a_change:
            existant.statut_contenu = "extrait_automatique"
        db.flush()
        return existant, False
    ligne = LegalAnnouncementGuide(**valeurs)
    db.add(ligne)
    db.flush()
    return ligne, True


def list_pending_validation(db: Session) -> list[LegalAnnouncementGuide]:
    return (
        db.query(LegalAnnouncementGuide)
        .filter(LegalAnnouncementGuide.statut_contenu == "extrait_automatique")
        .order_by(LegalAnnouncementGuide.collecte_le)
        .all()
    )


def list_valide_humain(db: Session) -> list[LegalAnnouncementGuide]:
    """Seules ces lignes sont chunkées/embeddées."""
    return (
        db.query(LegalAnnouncementGuide)
        .filter(LegalAnnouncementGuide.statut_contenu == "valide_humain")
        .order_by(LegalAnnouncementGuide.collecte_le)
        .all()
    )


def validate_guide(db: Session, guide_id: uuid.UUID) -> LegalAnnouncementGuide:
    """Passe en `valide_humain`. Ne commit jamais."""
    ligne = db.get(LegalAnnouncementGuide, guide_id)
    if ligne is None:
        raise LegalAnnouncementGuideNotFoundError(f"legal_announcement_guides.id={guide_id} introuvable.")
    ligne.statut_contenu = "valide_humain"
    db.flush()
    return ligne
