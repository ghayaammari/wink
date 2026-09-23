"""Orchestration du matching_agent pour un besoin (research_needs, service
7.7.2) — construit le contexte du besoin + les tools (chercheur_matching_
tools_service), appelle l'agent (agents/matching_agent/chercheur_matching_
service.py) et persiste le résultat (research_need_match_service.
upsert_result). Même séparation que les *_diagnostic_service.py de
compliance_agent : ce fichier ne fait plus de logique LLM lui-même.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.matching_agent.chercheur_matching_service import match_chercheurs
from backend.entrepreneur.services.project_service import get_owned_project
from backend.matching.models.research_need_match import ResearchNeedMatch
from backend.matching.services.chercheur_matching_tools_service import build_matching_agent_tools
from backend.matching.services.research_need_match_service import get_owned_need, upsert_result
from backend.shared.models.user import User


def run_matching(db: Session, user: User, project_id: UUID, need_id: UUID) -> ResearchNeedMatch:
    need = get_owned_need(db, user, project_id, need_id)
    project = get_owned_project(db, user, project_id)

    # Contexte du besoin, injecté directement dans le message de tâche de
    # l'agent -- plus de tool lire_besoin (CORRECTIF du 23/09/2026, voir
    # chercheur_matching_tools_service.py) : un aller-retour LLM de moins,
    # l'info étant de toute façon systématiquement nécessaire au 1er tour.
    besoin = {
        "type_besoin": need.type_besoin,
        "titre": need.titre,
        "description": need.description,
        "projet": {
            "secteur": project.sector,
            "description": project.description,
            "technologies": project.technologies,
            "value_proposition": project.value_proposition,
        },
    }

    seen_researcher_ids: list[str] = []
    tools = build_matching_agent_tools(db, seen_researcher_ids)

    result = match_chercheurs(tools, besoin)

    # Anti-hallucination : un researcher_profile_id renvoyé par l'agent qui
    # ne correspond à aucun id réellement vu via lister_chercheurs_
    # disponibles pendant ce run est écarté silencieusement — même principe
    # que la vérification des source_id côté compliance_agent
    # (seen_source_ids, voir *_diagnostic_service.py).
    matches_valides = [m for m in result.matches if m.researcher_profile_id in seen_researcher_ids]

    # "interesse" par défaut ici -- upsert_result reprend ensuite le flag de
    # l'ancien match du même chercheur s'il existait déjà (voir sa docstring),
    # cette valeur par défaut ne compte donc que pour un chercheur nouvellement
    # recommandé.
    matches_dicts = [
        {
            "researcher_profile_id": m.researcher_profile_id,
            "nom": m.nom,
            "rang": m.rang,
            "niveau_pertinence": m.niveau_pertinence,
            "explication": m.explication,
            "interesse": False,
        }
        for m in matches_valides
    ]

    return upsert_result(db, need.id, matches_dicts, result.synthese)
