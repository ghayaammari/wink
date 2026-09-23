"""Logique métier de `research_need_matches` — résultat persisté du
matching_agent pour un besoin (research_needs, service 7.7.2). Lecture/
upsert simples, même convention que project_fintech_gap_analysis_service.py
(get_result/upsert_result) : la génération elle-même (appel agent, tools)
vit dans chercheur_matching_orchestration_service.py, pas ici.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.services.project_service import get_owned_project
from backend.matching.models.research_need import ResearchNeed
from backend.matching.models.research_need_match import ResearchNeedMatch
from backend.matching.services.research_need_service import ResearchNeedNotFoundError
from backend.shared.models.user import User


def get_owned_need(db: Session, user: User, project_id: UUID, need_id: UUID) -> ResearchNeed:
    """Vérifie que ce besoin appartient bien au projet de cet entrepreneur —

    même contrôle que research_need_service (project_id + need_id), factorisé
    ici car réutilisé par tous les points d'entrée du matching (génération,
    lecture, marquage "intéressé", voir chercheur_matching_router.py)."""
    project = get_owned_project(db, user, project_id)
    need = db.query(ResearchNeed).filter(ResearchNeed.id == need_id, ResearchNeed.project_id == project.id).first()
    if need is None:
        raise ResearchNeedNotFoundError("Besoin introuvable.")
    return need


def get_result(db: Session, need_id: UUID) -> ResearchNeedMatch | None:
    """`None` tant que le matching n'a jamais été généré pour ce besoin —

    même raisonnement que get_result côté gap-analysis (pas de ligne = pas
    encore généré, jamais une ligne à moitié remplie)."""
    return db.query(ResearchNeedMatch).filter(ResearchNeedMatch.research_need_id == need_id).first()


def upsert_result(db: Session, need_id: UUID, matches: list[dict], synthese: str) -> ResearchNeedMatch:
    """Un nouveau clic ("Relancer le matching") régénère le résultat -- mais

    contrairement à avant, ne l'écrase plus complètement : chaque nouveau
    match reprend le flag `interesse` de l'ancien match du même chercheur
    (même researcher_profile_id) si l'entrepreneur l'avait marqué "intéressé"
    avant la régénération. Sans ça, relancer le matching effacerait
    silencieusement les intérêts déjà marqués, ce qui casserait la
    "Recommandations intéressantes" -- l'entrepreneur perdrait sa sélection
    à chaque relance sans le savoir."""
    row = db.query(ResearchNeedMatch).filter(ResearchNeedMatch.research_need_id == need_id).first()

    interesse_precedent: dict[str, bool] = {}
    if row is not None:
        interesse_precedent = {m["researcher_profile_id"]: m.get("interesse", False) for m in row.matches}

    matches_avec_interet = [
        {**m, "interesse": interesse_precedent.get(m["researcher_profile_id"], False)} for m in matches
    ]

    if row is None:
        row = ResearchNeedMatch(research_need_id=need_id)
        db.add(row)

    row.matches = matches_avec_interet
    row.synthese = synthese
    db.commit()
    db.refresh(row)
    return row


class MatchNotFoundError(ResearchNeedNotFoundError):
    """Le researcher_profile_id demandé n'apparaît pas dans les matches de ce besoin."""


def toggle_interet(db: Session, need_id: UUID, researcher_profile_id: UUID, interesse: bool) -> ResearchNeedMatch:
    """Marque/démarque un match comme "intéressé" -- `matches` est du JSONB

    (liste, pas une table à part) : SQLAlchemy ne détecte pas une mutation en
    place sur un attribut JSONB, il faut réassigner l'attribut entier pour
    que le changement soit persisté (même contrainte que toggle_obligation,
    project_fintech_gap_analysis_service.py)."""
    row = db.query(ResearchNeedMatch).filter(ResearchNeedMatch.research_need_id == need_id).first()
    if row is None:
        raise MatchNotFoundError("Aucun matching généré pour ce besoin.")

    researcher_id_str = str(researcher_profile_id)
    nouveaux_matches = []
    trouve = False
    for m in row.matches:
        if m["researcher_profile_id"] == researcher_id_str:
            trouve = True
            nouveaux_matches.append({**m, "interesse": interesse})
        else:
            nouveaux_matches.append(m)

    if not trouve:
        raise MatchNotFoundError("Ce chercheur ne fait pas partie des recommandations de ce besoin.")

    row.matches = nouveaux_matches
    db.commit()
    db.refresh(row)
    return row


def list_interesting_matches(db: Session, user: User, project_id: UUID) -> list[dict]:
    """Toutes les recommandations marquées "intéressé", tous besoins

    confondus, pour le projet de cet entrepreneur -- alimente la sous-partie
    "Recommandations intéressantes" du sidebar (une vue transversale, pas
    par besoin comme le reste de cette page)."""
    project = get_owned_project(db, user, project_id)
    rows = (
        db.query(ResearchNeedMatch, ResearchNeed)
        .join(ResearchNeed, ResearchNeed.id == ResearchNeedMatch.research_need_id)
        .filter(ResearchNeed.project_id == project.id)
        .all()
    )
    resultats: list[dict] = []
    for match_row, need in rows:
        for m in match_row.matches:
            if m.get("interesse"):
                resultats.append({"need_id": need.id, "need_titre": need.titre, "match": m})
    return resultats
