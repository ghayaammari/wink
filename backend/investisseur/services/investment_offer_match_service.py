"""Logique métier de `investment_offer_matches` — résultat persisté du

matching_agent_investisseur pour une offre (investment_offers). Lecture/
upsert simples, même convention que research_need_match_service.py.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_public_profile import ProjectPublicProfile
from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.models.investment_offer_match import InvestmentOfferMatch
from backend.investisseur.schemas.investment_offer_match_schemas import (
    InvestmentOfferMatchRead,
    StartupInteressanteRead,
)
from backend.investisseur.services.investment_offer_service import InvestmentOfferNotFoundError
from backend.investisseur.services.investor_service import get_by_user_id
from backend.shared.models.user import User


def get_result(db: Session, offer_id: UUID) -> InvestmentOfferMatch | None:
    """`None` tant que le matching n'a jamais été généré pour cette offre --

    même raisonnement que get_result côté research_need_match_service.py."""
    return db.query(InvestmentOfferMatch).filter(InvestmentOfferMatch.investment_offer_id == offer_id).first()


def upsert_result(db: Session, offer_id: UUID, matches: list[dict], synthese: str) -> InvestmentOfferMatch:
    """Un nouveau clic ("Relancer le matching") régénère le résultat, en

    reprenant le flag `interesse` de l'ancien match du même projet si
    l'investisseur l'avait déjà marqué "intéressé" -- même raisonnement que
    upsert_result côté research_need_match_service.py (ne jamais perdre
    silencieusement un intérêt déjà marqué)."""
    row = db.query(InvestmentOfferMatch).filter(InvestmentOfferMatch.investment_offer_id == offer_id).first()

    interesse_precedent: dict[str, bool] = {}
    if row is not None:
        interesse_precedent = {m["project_id"]: m.get("interesse", False) for m in row.matches}

    matches_avec_interet = [
        {**m, "interesse": interesse_precedent.get(m["project_id"], False)} for m in matches
    ]

    if row is None:
        row = InvestmentOfferMatch(investment_offer_id=offer_id)
        db.add(row)

    row.matches = matches_avec_interet
    row.synthese = synthese
    db.commit()
    db.refresh(row)
    return row


def _enrichir_matches(db: Session, matches: list[dict]) -> list[dict]:
    """Complète chaque match avec les données publiques du projet (secteur,

    stade, localisation, description, technologies, logo/site) -- lues EN
    DIRECT depuis `projects`/`project_public_profiles` à chaque lecture,
    jamais stockées dans le JSONB `matches` : l'agent ne connaît/n'écrit que
    ce qui sert au matching (nom/rang/niveau/explication) -- le reste vient
    de la fiche vivante du projet, pour ne jamais afficher une info perimee
    si la startup met à jour son profil après le calcul du matching. Un
    projet introuvable (supprimé entre temps) laisse simplement les champs
    a None plutot que de faire echouer l'affichage.
    """
    project_ids = [m["project_id"] for m in matches]
    if not project_ids:
        return matches

    rows = (
        db.query(Project, ProjectPublicProfile)
        .outerjoin(ProjectPublicProfile, ProjectPublicProfile.project_id == Project.id)
        .filter(Project.id.in_(project_ids))
        .all()
    )
    profils = {
        str(project.id): {
            "secteur": project.sector,
            "stade": project.stage,
            "localisation": project.localisation,
            "value_proposition": project.value_proposition,
            "technologies": project.technologies,
            "logo_url": public_profile.logo_url if public_profile else None,
            "website_url": public_profile.website_url if public_profile else None,
        }
        for project, public_profile in rows
    }
    return [{**m, **profils.get(m["project_id"], {})} for m in matches]


def enrichir_resultat(db: Session, row: InvestmentOfferMatch) -> InvestmentOfferMatchRead:
    """Construit la réponse API d'un résultat de matching, complétée par

    _enrichir_matches -- utilisé par les 3 routes qui renvoient un
    InvestmentOfferMatchRead (lancer/lire/marquer_interet). Construit le
    schéma explicitement (pas de `response_model` depuis l'objet ORM en
    l'état) pour ne jamais muter/committer `row.matches` par accident.
    """
    return InvestmentOfferMatchRead(
        id=row.id,
        investment_offer_id=row.investment_offer_id,
        matches=_enrichir_matches(db, row.matches),
        synthese=row.synthese,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_interesting_matches_enrichies(db: Session, user: User) -> list[StartupInteressanteRead]:
    """Version enrichie de list_interesting_matches, pour la route

    GET /investisseur/offres/interessantes -- même raisonnement
    d'enrichissement en lecture que enrichir_resultat, mais en un seul
    aller-retour DB pour toutes les offres de l'investisseur plutôt qu'un
    par match.
    """
    bruts = list_interesting_matches(db, user)
    matches_enrichis = _enrichir_matches(db, [r["match"] for r in bruts])
    return [
        StartupInteressanteRead(offer_id=r["offer_id"], offer_titre=r["offer_titre"], match=m)
        for r, m in zip(bruts, matches_enrichis)
    ]


class MatchNotFoundError(InvestmentOfferNotFoundError):
    """Le project_id demandé n'apparaît pas dans les matches de cette offre."""


def toggle_interet(db: Session, offer_id: UUID, project_id: UUID, interesse: bool) -> InvestmentOfferMatch:
    """Marque/démarque un match comme "intéressé" -- réassigne `matches`

    entièrement (JSONB, SQLAlchemy ne détecte pas une mutation en place),
    même contrainte que toggle_interet côté research_need_match_service.py."""
    row = db.query(InvestmentOfferMatch).filter(InvestmentOfferMatch.investment_offer_id == offer_id).first()
    if row is None:
        raise MatchNotFoundError("Aucun matching généré pour cette offre.")

    project_id_str = str(project_id)
    nouveaux_matches = []
    trouve = False
    for m in row.matches:
        if m["project_id"] == project_id_str:
            trouve = True
            nouveaux_matches.append({**m, "interesse": interesse})
        else:
            nouveaux_matches.append(m)

    if not trouve:
        raise MatchNotFoundError("Ce projet ne fait pas partie des recommandations de cette offre.")

    row.matches = nouveaux_matches
    db.commit()
    db.refresh(row)
    return row


def list_interesting_matches(db: Session, user: User) -> list[dict]:
    """Toutes les recommandations marquées "intéressé", toutes offres

    confondues, pour l'investisseur connecté -- alimente la page "Startups
    intéressantes"."""
    profile = get_by_user_id(db, user.id)
    rows = (
        db.query(InvestmentOfferMatch, InvestmentOffer)
        .join(InvestmentOffer, InvestmentOffer.id == InvestmentOfferMatch.investment_offer_id)
        .filter(InvestmentOffer.investor_profile_id == profile.id)
        .all()
    )
    resultats: list[dict] = []
    for match_row, offer in rows:
        for m in match_row.matches:
            if m.get("interesse"):
                resultats.append({"offer_id": offer.id, "offer_titre": offer.titre, "match": m})
    return resultats
