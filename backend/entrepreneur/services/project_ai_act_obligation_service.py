"""Logique métier de `project_ai_act_obligations` (+ archivage dans

`project_ai_act_obligations_history`) — service 3.3.12 (AI Act). Copie
conforme de `project_rgpd_obligation_service.py`, sans le flag `lie_a_aipd`
(pas d'équivalent AI Act, voir modèle) — même règle "jamais écraser un fait",
non répétée ici en détail.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_ai_act_obligation import ProjectAiActObligation
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.models.project_ai_act_obligation_history import ProjectAiActObligationHistory
from backend.entrepreneur.schemas.project_ai_act_obligation_schemas import AiActObligationCandidate
from backend.entrepreneur.services.compliance_report_service import ObligationRapport, build_obligations_report_pdf
from backend.entrepreneur.services.compliance_score_service import compute_compliance_score
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


class AiActObligationNotFoundError(Exception):
    """Traduite en 404 par le router — obligation_id inconnu de ce projet."""


def list_obligations(db: Session, user: User, project_id: UUID) -> list[ProjectAiActObligation]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(ProjectAiActObligation)
        .filter(ProjectAiActObligation.project_id == project.id)
        .order_by(ProjectAiActObligation.created_at)
        .all()
    )


def mark_statut(
    db: Session, user: User, project_id: UUID, obligation_id: UUID, statut: str
) -> ProjectAiActObligation:
    project = get_owned_project(db, user, project_id)
    obligation = (
        db.query(ProjectAiActObligation)
        .filter(ProjectAiActObligation.id == obligation_id, ProjectAiActObligation.project_id == project.id)
        .first()
    )
    if obligation is None:
        raise AiActObligationNotFoundError("Obligation introuvable.")

    obligation.statut = statut
    db.commit()
    db.refresh(obligation)
    return obligation


def get_score(db: Session, user: User, project_id: UUID) -> ComplianceScoreRead:
    """Score de conformité AI Act : même principe que la version RGPD

    (project_rgpd_obligation_service.get_score), non répété en détail ici.
    """
    obligations = list_obligations(db, user, project_id)
    accomplies = [o.statut == "fait" for o in obligations]
    return ComplianceScoreRead(
        score=compute_compliance_score(accomplies),
        total_obligations=len(accomplies),
        obligations_accomplies=sum(accomplies),
    )


def get_report_pdf(db: Session, user: User, project_id: UUID) -> bytes:
    """Meme principe que la version RGPD (project_rgpd_obligation_service.

    get_report_pdf), non repete en detail ici."""
    obligations = list_obligations(db, user, project_id)
    score = compute_compliance_score([o.statut == "fait" for o in obligations])
    rapport_obligations = [
        ObligationRapport(nom=o.nom, description=o.description, accompli=o.statut == "fait") for o in obligations
    ]
    return build_obligations_report_pdf(
        titre="Rapport de conformite AI Act", obligations=rapport_obligations, score=score
    )


def sync_obligations(
    db: Session, project_id: UUID, candidates: list[AiActObligationCandidate]
) -> list[ProjectAiActObligation]:
    """Régénération majeure, appelée uniquement par ai_act_diagnostic_service

    (project_id déjà validé en amont — pas de get_owned_project ici, même
    convention que la version RGPD)."""
    existing = {
        o.nom: o for o in db.query(ProjectAiActObligation).filter(ProjectAiActObligation.project_id == project_id)
    }
    candidate_noms = {c.nom for c in candidates}

    for nom, obligation in existing.items():
        if nom not in candidate_noms:
            db.add(
                ProjectAiActObligationHistory(
                    project_id=project_id,
                    nom=obligation.nom,
                    description=obligation.description,
                    statut=obligation.statut,
                )
            )
            db.delete(obligation)

    for candidate in candidates:
        obligation = existing.get(candidate.nom)
        if obligation is None:
            db.add(
                ProjectAiActObligation(
                    project_id=project_id,
                    nom=candidate.nom,
                    description=candidate.description,
                    legal_text_id=candidate.legal_text_id,
                )
            )
        else:
            obligation.description = candidate.description
            obligation.legal_text_id = candidate.legal_text_id
            # statut volontairement non touché : "jamais écraser un fait".

    db.commit()
    return list(db.query(ProjectAiActObligation).filter(ProjectAiActObligation.project_id == project_id).all())
