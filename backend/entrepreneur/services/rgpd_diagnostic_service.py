"""Orchestration du diagnostic RGPD — service 3.3.1. Version agentique :

construit les tools du compliance_agent (profil, corpus RGPD) et le laisse
décider lui-même quoi lire/rechercher, avant de résoudre chaque source_id en
`legal_text_id` réel et persister via
project_rgpd_obligation_service.sync_obligations.

Avant cette conversion, une recherche vectorielle avec un "socle universel"
de thèmes (voir _THEMES_SOCLE, ancienne version) garantissait que même un
profil vide remontait les obligations de base (registre, base légale...).
Cette garantie est maintenant portée par le system prompt de l'agent (voir
compliance_agent_rgpd.system dans prompts.yaml), qui lui demande
explicitement de rechercher aussi ces obligations de base avant de conclure
à une liste vide.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.rgpd_service import ObligationCandidate, generate_rgpd_obligations
from backend.entrepreneur.models.project_rgpd_obligation import ProjectRgpdObligation
from backend.entrepreneur.schemas.project_rgpd_obligation_schemas import RgpdObligationCandidate
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.project_rgpd_obligation_service import sync_obligations
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.knowledge_base.services.content_embeddings_service import resolve_legal_text_id
from backend.shared.models.user import User


def _to_backend_candidate(
    candidate: ObligationCandidate, db: Session, seen_source_ids: list[str]
) -> RgpdObligationCandidate:
    """Résout `source_id` (vérifié réellement vu pendant ce run via

    seen_source_ids) en `legal_text_id` réel -- même raisonnement que
    _to_backend_candidate (ai_act_diagnostic_service.py)."""
    legal_text_id = None
    if candidate.source_id is not None and candidate.source_id in seen_source_ids:
        legal_text_id = resolve_legal_text_id(db, source_id=candidate.source_id)
    return RgpdObligationCandidate(
        nom=candidate.nom,
        description=candidate.description,
        legal_text_id=legal_text_id,
        lie_a_aipd=candidate.lie_a_aipd,
    )


def run_diagnostic(db: Session, user: User, project_id: UUID) -> list[ProjectRgpdObligation]:
    """Point d'entrée du service 3.3.1 : recalcule les obligations RGPD

    applicables à partir de l'état courant du profil, et les persiste. À
    appeler quand le profil change de façon significative (voir docstring de
    `project_rgpd_obligations_history` — pas à chaque frappe) : c'est à
    l'appelant (future route) de décider quand déclencher ce recalcul, pas à
    cette fonction.
    """
    project = get_owned_project(db, user, project_id)

    seen_source_ids: list[str] = []
    tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)
    result = generate_rgpd_obligations(tools)
    candidates = [_to_backend_candidate(candidate, db, seen_source_ids) for candidate in result.obligations]

    return sync_obligations(db, project.id, candidates)
