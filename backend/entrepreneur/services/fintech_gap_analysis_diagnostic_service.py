"""Orchestration du diagnostic d'écart FinTech — service 3.3.6, bloc unique

(pas de chapitres, contrairement à healthtech_gap_analysis_diagnostic_
service.py). Version agentique (même conversion que healthtech) : construit
les tools du compliance_agent et le laisse décider lui-même quoi
lire/rechercher, avant de persister via
project_fintech_gap_analysis_service.upsert_result.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.fintech_gap_analysis_service import generate_gap_analysis
from backend.entrepreneur.models.project_fintech_gap_analysis import ProjectFintechGapAnalysis
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.project_fintech_classification_service import get_or_create_classification
from backend.entrepreneur.services.project_fintech_gap_analysis_service import (
    ensure_classification_complete,
    upsert_result,
)
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def _obligations_to_dict(obligations, seen_source_ids: list[str]) -> list[dict]:
    """Même raisonnement que healthtech_gap_analysis_diagnostic_service.

    _obligations_to_dict : ne garde un source_id que s'il correspond bien à
    un chunk réellement vu par l'agent pendant ce run."""
    seen = set(seen_source_ids)
    result = []
    for obligation in obligations:
        source_id = obligation.source_id if obligation.source_id in seen else None
        result.append(
            {"nom": obligation.nom, "description": obligation.description, "source_id": source_id, "accompli": False}
        )
    return result


def run_diagnostic(db: Session, user: User, project_id: UUID) -> ProjectFintechGapAnalysis:
    """Point d'entrée du service 3.3.6 (volet FinTech) : déclenché uniquement

    par un clic explicite côté frontend — chaque appel coûte un vrai appel
    LLM, contrairement au recalcul gratuit de la classification. Pas de
    verrouillage à vérifier ici (pas de chapitres, voir docstring module).
    """
    project = get_owned_project(db, user, project_id)
    ensure_classification_complete(db, user, project.id)
    # Toujours calculee avant l'appel a l'agent (garantit que le tool
    # lire_profil_projet trouvera bien une classification a jour) meme si
    # cette fonction n'utilise plus directement son retour ci-dessous.
    get_or_create_classification(db, user, project.id)

    seen_source_ids: list[str] = []
    tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)
    result = generate_gap_analysis(tools)
    obligations = _obligations_to_dict(result.obligations, seen_source_ids)

    return upsert_result(db, project.id, {"obligations": obligations}, result.justification)
