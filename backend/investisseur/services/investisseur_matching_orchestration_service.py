"""Orchestration du matching_agent_investisseur pour une offre

(investment_offers, EPIC-07) — construit le contexte de l'offre + les
tools (investisseur_matching_tools_service), appelle l'agent (agents/
matching_agent/investisseur_matching_service.py) et persiste le résultat
(investment_offer_match_service.upsert_result). Même séparation que
chercheur_matching_orchestration_service.py.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.matching_agent.investisseur_matching_service import match_startups
from backend.investisseur.models.investment_offer_match import InvestmentOfferMatch
from backend.investisseur.services.investisseur_matching_tools_service import build_investisseur_matching_tools
from backend.investisseur.services.investment_offer_match_service import upsert_result
from backend.investisseur.services.investment_offer_service import get_owned_offer
from backend.investisseur.services.investor_service import get_by_user_id
from backend.shared.models.user import User


def run_matching(db: Session, user: User, offer_id: UUID) -> InvestmentOfferMatch:
    offer = get_owned_offer(db, user, offer_id)
    profile = get_by_user_id(db, user.id)

    # Contexte de l'offre, injecté directement dans le message de tâche de
    # l'agent (même optimisation que chercheur_matching_orchestration_
    # service.py, CORRECTIF v3 -- pas de tool lire_offre).
    offre = {
        "titre": offer.titre,
        "description": offer.description,
        "montant_propose": offer.montant_propose,
        "secteurs_cibles": offer.secteurs_cibles,
        "stades_cibles": offer.stades_cibles,
        "investisseur": {
            "investor_type": profile.investor_type,
            "investment_thesis": profile.investment_thesis,
        },
    }

    seen_project_ids: list[str] = []
    tools = build_investisseur_matching_tools(db, seen_project_ids)

    result = match_startups(tools, offre)

    # Anti-hallucination : un project_id renvoyé par l'agent qui ne
    # correspond à aucun id réellement vu via lister_projets_disponibles
    # pendant ce run est écarté silencieusement -- même principe que
    # matches_valides côté chercheur_matching_orchestration_service.py.
    matches_valides = [m for m in result.matches if m.project_id in seen_project_ids]

    matches_dicts = [
        {
            "project_id": m.project_id,
            "nom": m.nom,
            "rang": m.rang,
            "niveau_pertinence": m.niveau_pertinence,
            "explication": m.explication,
            "interesse": False,
        }
        for m in matches_valides
    ]

    return upsert_result(db, offer.id, matches_dicts, result.synthese)
