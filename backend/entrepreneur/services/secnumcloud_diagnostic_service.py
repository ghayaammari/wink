"""Orchestration du parcours SecNumCloud — service 3.3.11. Même schéma que

rgpd_diagnostic_service.py : construit les tools génériques du compliance_agent
(déjà partagés entre tous les sous-domaines, voir compliance_agent_tools_service.py
-- aucune modification nécessaire pour SecNumCloud, rechercher_corpus_reglementaire
accepte n'importe quel domaine), laisse l'agent décider quoi lire/rechercher,
puis résout chaque source_id en `legal_text_id` réel avant de persister à la
fois les étapes (project_certification_obligation_service.sync_obligations)
et l'estimation (project_certification_estimation_service.save_estimation) --
un seul run d'agent produit les deux, voir docstring de
agents/compliance_agent/secnumcloud_service.py.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.secnumcloud_service import (
    CertificationObligationCandidate as AgentObligationCandidate,
    generate_secnumcloud_parcours,
)
from backend.entrepreneur.models.project_certification_estimation import ProjectCertificationEstimation
from backend.entrepreneur.models.project_certification_obligation import ProjectCertificationObligation
from backend.entrepreneur.schemas.project_certification_obligation_schemas import CertificationObligationCandidate
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.project_certification_estimation_service import save_estimation
from backend.entrepreneur.services.project_certification_obligation_service import sync_obligations
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.knowledge_base.services.content_embeddings_service import resolve_legal_text_id
from backend.shared.models.user import User


def _to_backend_candidate(
    candidate: AgentObligationCandidate, db: Session, seen_source_ids: list[str]
) -> CertificationObligationCandidate:
    """Résout `source_id` (vérifié réellement vu pendant ce run via

    seen_source_ids) en `legal_text_id` réel -- même raisonnement que
    _to_backend_candidate (rgpd_diagnostic_service.py)."""
    legal_text_id = None
    if candidate.source_id is not None and candidate.source_id in seen_source_ids:
        legal_text_id = resolve_legal_text_id(db, source_id=candidate.source_id)
    return CertificationObligationCandidate(
        nom=candidate.nom,
        description=candidate.description,
        ordre=candidate.ordre,
        legal_text_id=legal_text_id,
    )


def run_diagnostic(
    db: Session, user: User, project_id: UUID
) -> tuple[list[ProjectCertificationObligation], ProjectCertificationEstimation]:
    """Point d'entrée du service 3.3.11 : génère le parcours SecNumCloud

    (étapes ordonnées + estimation délai/coût) à partir du corpus ANSSI et du
    profil du projet, et le persiste. À appeler explicitement par
    l'entrepreneur (bouton dédié), jamais automatiquement -- même convention
    que rgpd_diagnostic_service.run_diagnostic.
    """
    project = get_owned_project(db, user, project_id)

    seen_source_ids: list[str] = []
    # inclure_questionnaires_generaux=False -- CORRECTIF du 22/09/2026 (v5,
    # voir compliance_agent_tools_service.py) : SecNumCloud n'utilise que
    # "stage" du profil, jamais les questionnaires RGPD/AI Act (~11 champs
    # sans rapport, poids mort dans l'historique du run).
    tools = build_compliance_agent_tools(
        db, user, project.id, seen_source_ids, inclure_questionnaires_generaux=False
    )
    result = generate_secnumcloud_parcours(tools)

    candidates = [_to_backend_candidate(candidate, db, seen_source_ids) for candidate in result.obligations]
    obligations = sync_obligations(db, project.id, candidates)

    estimation = save_estimation(
        db,
        project.id,
        delai_mois_min=result.estimation.delai_mois_min,
        delai_mois_max=result.estimation.delai_mois_max,
        cout_estime_min=result.estimation.cout_estime_min,
        cout_estime_max=result.estimation.cout_estime_max,
        justification=result.estimation.justification,
    )

    return obligations, estimation
