"""Logique métier de `project_sector_detection` — service 3.3.5, étape 0.

Get-or-create (même pattern que le profil AI Act) + upsert du résultat de
détection, appelé uniquement par `sector_detection_diagnostic_service.
run_detection()`. Même convention que
`project_ai_act_classification_service.py`.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_sector_detection import ProjectSectorDetection
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_detection(db: Session, user: User, project_id: UUID) -> ProjectSectorDetection:
    project = get_owned_project(db, user, project_id)

    detection = (
        db.query(ProjectSectorDetection).filter(ProjectSectorDetection.project_id == project.id).first()
    )
    if detection is None:
        detection = ProjectSectorDetection(project_id=project.id)
        db.add(detection)
        db.commit()
        db.refresh(detection)
    return detection


def upsert_detection(
    db: Session, project_id: UUID, secteur_detecte: str, justification: str
) -> ProjectSectorDetection:
    """Appelé côté serveur par `sector_detection_diagnostic_service`,

    `project_id` déjà validé en amont — pas de `get_owned_project` ici (même
    convention que `upsert_classification`,
    `project_ai_act_classification_service.py`)."""
    detection = (
        db.query(ProjectSectorDetection).filter(ProjectSectorDetection.project_id == project_id).first()
    )
    if detection is None:
        detection = ProjectSectorDetection(project_id=project_id)
        db.add(detection)

    detection.secteur_detecte = secteur_detecte
    detection.justification = justification
    db.commit()
    db.refresh(detection)
    return detection
