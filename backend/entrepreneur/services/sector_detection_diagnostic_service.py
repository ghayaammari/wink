"""Orchestration de la détection de secteur — service 3.3.5, étape 0. Rôle

équivalent à `ai_act_diagnostic_service.py` (version agentique) : construit
les tools du compliance_agent et le laisse lire lui-même le profil du projet
(secteur déclaré, description), avant de persister via
`project_sector_detection_service.upsert_detection`.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.sector_detection_service import detect_sector
from backend.entrepreneur.schemas.project_sector_detection_schemas import ProjectSectorDetectionRead
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.project_sector_detection_service import upsert_detection
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def run_detection(db: Session, user: User, project_id: UUID) -> ProjectSectorDetectionRead:
    """Point d'entrée du service 3.3.5, étape 0. Déclenché explicitement par

    un bouton dédié côté frontend (même convention que POST .../ai-act/
    diagnostic) — jamais automatiquement, pour ne pas multiplier les appels
    LLM à chaque visite de la page.
    """
    project = get_owned_project(db, user, project_id)

    seen_source_ids: list[str] = []
    tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)
    result = detect_sector(tools)

    return upsert_detection(db, project.id, result.secteur_detecte, result.justification)
