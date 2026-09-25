"""Logique metier du profil `project_pitch_profiles` — service 6.6.2 (pitch

deck). Get-or-create + PATCH via exclude_unset, meme principe que
ai_act_data_profile_service.py, non repete ici en detail.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_pitch_profile import ProjectPitchProfile
from backend.entrepreneur.schemas.pitch_schemas import ProjectPitchProfileUpdate
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def get_or_create_profile(db: Session, user: User, project_id: UUID) -> ProjectPitchProfile:
    project = get_owned_project(db, user, project_id)

    profile = db.query(ProjectPitchProfile).filter(ProjectPitchProfile.project_id == project.id).first()
    if profile is None:
        profile = ProjectPitchProfile(project_id=project.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def update_profile(db: Session, user: User, project_id: UUID, data: ProjectPitchProfileUpdate) -> ProjectPitchProfile:
    profile = get_or_create_profile(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile
