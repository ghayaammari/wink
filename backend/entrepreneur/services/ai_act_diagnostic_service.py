"""Orchestration du diagnostic AI Act — service 3.3.12. Version agentique :

construit les tools du compliance_agent (contexte projet, profil IA, corpus
AI Act) et le laisse decider lui-meme quoi lire/rechercher, avant de
resoudre chaque source_id en `legal_text_id` reel et persister via
project_ai_act_classification_service.upsert_classification et
project_ai_act_obligation_service.sync_obligations.

Différence structurelle avec le RGPD (voir docstring ai_act_data_profile.py) :
pas de "socle universel" — un projet qui n'utilise pas l'IA n'a par
définition aucune obligation AI Act. Le court-circuit ci-dessous
(`utilise_ia is False`) évite tout appel LLM pour ce cas.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.ai_act_service import ObligationCandidate, generate_ai_act_diagnostic
from backend.entrepreneur.schemas.project_ai_act_obligation_schemas import AiActDiagnosticRunResult, AiActObligationCandidate
from backend.entrepreneur.services.ai_act_data_profile_service import get_or_create_profile
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.project_ai_act_classification_service import upsert_classification
from backend.entrepreneur.services.project_ai_act_obligation_service import sync_obligations
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.knowledge_base.services.content_embeddings_service import resolve_legal_text_id
from backend.shared.models.user import User


def _to_backend_candidate(
    candidate: ObligationCandidate, db: Session, seen_source_ids: list[str]
) -> AiActObligationCandidate:
    """Resout `source_id` (verifie reellement vu pendant ce run via

    seen_source_ids) en `legal_text_id` reel -- meme raisonnement que
    _obligations_to_dict (healthtech_gap_analysis_diagnostic_service.py),
    avec une resolution en plus vers un vrai UUID (l'AI Act a une table
    d'obligations avec une FK legal_text_id, contrairement a HealthTech qui
    stocke juste un source_id texte).
    """
    legal_text_id = None
    if candidate.source_id is not None and candidate.source_id in seen_source_ids:
        legal_text_id = resolve_legal_text_id(db, source_id=candidate.source_id)
    return AiActObligationCandidate(nom=candidate.nom, description=candidate.description, legal_text_id=legal_text_id)


def run_diagnostic(db: Session, user: User, project_id: UUID) -> AiActDiagnosticRunResult:
    """Point d'entrée du service 3.3.12. Déclenché explicitement par un

    bouton dédié côté frontend (même convention que POST .../rgpd/diagnostic)
    — jamais automatiquement après chaque PATCH du profil.
    """
    project = get_owned_project(db, user, project_id)
    profile = get_or_create_profile(db, user, project_id)

    if profile.utilise_ia is False:
        # Court-circuit : fait structurel, pas un jugement — voir docstring
        # module. Aucun appel LLM.
        classification = upsert_classification(
            db,
            project.id,
            "minimal",
            "Projet declare comme n'utilisant aucun systeme d'intelligence artificielle : "
            "le reglement (UE) 2024/1689 ne s'applique pas.",
        )
        obligations = sync_obligations(db, project.id, [])
        return AiActDiagnosticRunResult(classification=classification, obligations=obligations)

    seen_source_ids: list[str] = []
    tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)
    result = generate_ai_act_diagnostic(tools)
    candidates = [_to_backend_candidate(candidate, db, seen_source_ids) for candidate in result.obligations]

    classification = upsert_classification(db, project.id, result.categorie_risque, result.justification)
    obligations = sync_obligations(db, project.id, candidates)
    return AiActDiagnosticRunResult(classification=classification, obligations=obligations)
