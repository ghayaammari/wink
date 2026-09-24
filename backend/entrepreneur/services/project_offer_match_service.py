"""Logique métier de `project_offer_matches` — résultat persisté du

matching_agent_startup pour LE PROJET de l'entrepreneur (Startup -> Offres,
sens inverse de investment_offer_match_service.py). Lecture/upsert simples,
même convention que ce fichier miroir.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_offer_match import ProjectOfferMatch
from backend.entrepreneur.schemas.project_offer_match_schemas import OfferMatchRead, ProjectOfferMatchRead
from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.models.investor_profile import InvestorProfile


class ProjectOfferMatchError(Exception):
    """Erreur métier générique de ce module."""


class MatchNotFoundError(ProjectOfferMatchError):
    """L'offer_id demandé n'apparaît pas dans les matches de ce projet, ou

    aucun matching n'a jamais été généré pour ce projet."""


def get_result(db: Session, project_id: UUID) -> ProjectOfferMatch | None:
    """`None` tant que le matching n'a jamais été généré pour ce projet --

    même raisonnement que get_result côté investment_offer_match_service.py."""
    return db.query(ProjectOfferMatch).filter(ProjectOfferMatch.project_id == project_id).first()


def upsert_result(db: Session, project_id: UUID, matches: list[dict], synthese: str) -> ProjectOfferMatch:
    """Un nouveau clic ("Visualiser les offres") régénère le résultat, en

    reprenant le flag `interesse` de l'ancien match de la même offre si
    l'entrepreneur l'avait déjà marquée "intéressante" -- même raisonnement
    que upsert_result côté investment_offer_match_service.py (ne jamais
    perdre silencieusement un intérêt déjà marqué)."""
    row = db.query(ProjectOfferMatch).filter(ProjectOfferMatch.project_id == project_id).first()

    interesse_precedent: dict[str, bool] = {}
    if row is not None:
        interesse_precedent = {m["offer_id"]: m.get("interesse", False) for m in row.matches}

    matches_avec_interet = [
        {**m, "interesse": interesse_precedent.get(m["offer_id"], False)} for m in matches
    ]

    if row is None:
        row = ProjectOfferMatch(project_id=project_id)
        db.add(row)

    row.matches = matches_avec_interet
    row.synthese = synthese
    db.commit()
    db.refresh(row)
    return row


def toggle_interet(db: Session, project_id: UUID, offer_id: UUID, interesse: bool) -> ProjectOfferMatch:
    """Marque/démarque une offre comme "intéressante" -- réassigne `matches`

    entièrement (JSONB, SQLAlchemy ne détecte pas une mutation en place),
    même contrainte que toggle_interet côté investment_offer_match_service.py."""
    row = db.query(ProjectOfferMatch).filter(ProjectOfferMatch.project_id == project_id).first()
    if row is None:
        raise MatchNotFoundError("Aucun matching généré pour ce projet.")

    offer_id_str = str(offer_id)
    nouveaux_matches = []
    trouve = False
    for m in row.matches:
        if m["offer_id"] == offer_id_str:
            trouve = True
            nouveaux_matches.append({**m, "interesse": interesse})
        else:
            nouveaux_matches.append(m)

    if not trouve:
        raise MatchNotFoundError("Cette offre ne fait pas partie des recommandations de ce projet.")

    row.matches = nouveaux_matches
    db.commit()
    db.refresh(row)
    return row


def _enrichir_matches(db: Session, matches: list[dict]) -> list[dict]:
    """Complète chaque match avec les données publiques de l'offre (titre,

    montant, secteurs/stades ciblés, type d'investisseur, statut) -- lues EN
    DIRECT depuis `investment_offers`/`investor_profiles` à chaque lecture,
    jamais stockées dans le JSONB `matches` : l'agent ne connaît/n'écrit que
    ce qui sert au matching (rang/niveau/explication) -- le reste vient de
    la fiche vivante de l'offre, notamment `statut` : une offre fermée par
    l'investisseur entre-temps ne doit jamais paraître encore ouverte a
    l'entrepreneur. Une offre introuvable (supprimée) laisse simplement les
    champs à None plutôt que de faire échouer l'affichage.
    """
    offer_ids = [m["offer_id"] for m in matches]
    if not offer_ids:
        return matches

    rows = (
        db.query(InvestmentOffer, InvestorProfile)
        .join(InvestorProfile, InvestorProfile.id == InvestmentOffer.investor_profile_id)
        .filter(InvestmentOffer.id.in_(offer_ids))
        .all()
    )
    profils = {
        str(offer.id): {
            "titre": offer.titre,
            "montant_propose": offer.montant_propose,
            "secteurs_cibles": offer.secteurs_cibles,
            "stades_cibles": offer.stades_cibles,
            "investor_type": investor.investor_type,
            "statut": offer.statut,
        }
        for offer, investor in rows
    }
    return [{**m, **profils.get(m["offer_id"], {})} for m in matches]


def enrichir_resultat(db: Session, row: ProjectOfferMatch) -> ProjectOfferMatchRead:
    """Construit la réponse API d'un résultat de matching, complétée par

    _enrichir_matches -- utilisé par les 3 routes qui renvoient un
    ProjectOfferMatchRead (lancer/lire/marquer_interet). Construit le
    schéma explicitement (pas de `response_model` depuis l'objet ORM en
    l'état) pour ne jamais muter/committer `row.matches` par accident.
    """
    return ProjectOfferMatchRead(
        id=row.id,
        project_id=row.project_id,
        matches=_enrichir_matches(db, row.matches),
        synthese=row.synthese,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_offres_interessantes(db: Session, project_id: UUID) -> list[OfferMatchRead]:
    """Les offres marquées "intéressantes" pour ce projet -- alimente la

    page "Offres intéressantes". Contrairement au côté investisseur (qui
    doit agréger plusieurs offres, chacune avec son propre feed), un projet
    n'a qu'UN SEUL feed d'offres : filtrer les matches déjà marqués suffit,
    pas besoin d'un aller-retour cross-lignes supplémentaire.
    """
    row = get_result(db, project_id)
    if row is None:
        return []
    matches_interessants = [m for m in row.matches if m.get("interesse")]
    return [OfferMatchRead(**m) for m in _enrichir_matches(db, matches_interessants)]
