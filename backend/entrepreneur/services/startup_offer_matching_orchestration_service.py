"""Orchestration du matching_agent_startup pour LE PROJET d'un entrepreneur

(EPIC-06) — construit le contexte du projet + les tools (startup_offer_
matching_tools_service), appelle l'agent (agents/matching_agent/startup_
offer_matching_service.py) et persiste le résultat (project_offer_match_
service.upsert_result). Même séparation que investisseur_matching_
orchestration_service.py, sens inverse.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.matching_agent.startup_offer_matching_service import match_offers
from backend.entrepreneur.models.project_offer_match import ProjectOfferMatch
from backend.entrepreneur.services.project_offer_match_service import upsert_result
from backend.entrepreneur.services.project_service import get_owned_project
from backend.entrepreneur.services.startup_offer_matching_tools_service import build_startup_offer_matching_tools
from backend.shared.models.user import User


def run_matching(db: Session, user: User, project_id: UUID) -> ProjectOfferMatch:
    project = get_owned_project(db, user, project_id)

    # Contexte du projet, injecté directement dans le message de tâche de
    # l'agent (même optimisation que investisseur_matching_orchestration_
    # service.py, CORRECTIF v3 -- pas de tool lire_projet).
    projet = {
        "stage": project.stage,
        "secteur": project.sector,
        "sous_secteurs": project.subsectors,
        "technologies": project.technologies,
        "value_proposition": project.value_proposition,
        "description": project.description,
    }

    seen_offer_ids: list[str] = []
    tools = build_startup_offer_matching_tools(db, seen_offer_ids)

    result = match_offers(tools, projet)

    # Anti-hallucination : un offer_id renvoyé par l'agent qui ne
    # correspond à aucun id réellement vu via lister_offres_disponibles
    # pendant ce run est écarté silencieusement -- même principe que
    # matches_valides côté investisseur_matching_orchestration_service.py.
    matches_valides = [m for m in result.matches if m.offer_id in seen_offer_ids]

    matches_dicts = [
        {
            "offer_id": m.offer_id,
            "rang": m.rang,
            "niveau_pertinence": m.niveau_pertinence,
            "explication": m.explication,
            "interesse": False,
        }
        for m in matches_valides
    ]

    return upsert_result(db, project.id, matches_dicts, result.synthese)
