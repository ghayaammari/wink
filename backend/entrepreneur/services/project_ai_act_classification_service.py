"""Logique métier de `project_ai_act_classification` — service 3.3.12 (AI

Act). Get-or-create (même pattern que le profil) + upsert du résultat de
diagnostic, appelé uniquement par ai_act_diagnostic_service.run_diagnostic().
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_ai_act_classification import ProjectAiActClassification
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_classification(db: Session, user: User, project_id: UUID) -> ProjectAiActClassification:
    project = get_owned_project(db, user, project_id)

    classification = (
        db.query(ProjectAiActClassification).filter(ProjectAiActClassification.project_id == project.id).first()
    )
    if classification is None:
        classification = ProjectAiActClassification(project_id=project.id)
        db.add(classification)
        db.commit()
        db.refresh(classification)
    return classification


def upsert_classification(
    db: Session, project_id: UUID, categorie_risque: str, justification: str
) -> ProjectAiActClassification:
    """Appelé côté serveur par ai_act_diagnostic_service, project_id déjà

    validé en amont — pas de get_owned_project ici (même convention que
    sync_obligations, project_rgpd_obligation_service.py)."""
    classification = db.query(ProjectAiActClassification).filter(
        ProjectAiActClassification.project_id == project_id
    ).first()
    if classification is None:
        classification = ProjectAiActClassification(project_id=project_id)
        db.add(classification)

    classification.categorie_risque = categorie_risque
    classification.justification = justification
    db.commit()
    db.refresh(classification)
    return classification
