"""Logique métier de `research_needs` — service 7.7.1.

CRUD simple, pas de logique de matching ici (le feed proprement dit sera un
service séparé, une fois `agents/matching_agent/chercheur_matching_service.py`
construit -- décision actée en conversation produit : matching_agent, un
dossier avec un fichier par sous-domaine chercheur/investisseur, chacun agent
one-shot avec ses propres tools, pas encore codé). Ce fichier ne fait que
créer/lister/fermer un besoin.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.matching.models.research_need import ResearchNeed
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


class ResearchNeedNotFoundError(Exception):
    """Traduite en 404 par le router — need_id inconnu de ce projet."""


def create_need(
    db: Session, user: User, project_id: UUID, type_besoin: str, titre: str, description: str
) -> ResearchNeed:
    project = get_owned_project(db, user, project_id)
    need = ResearchNeed(
        project_id=project.id,
        type_besoin=type_besoin,
        titre=titre,
        description=description,
    )
    db.add(need)
    db.commit()
    db.refresh(need)
    return need


def list_needs(db: Session, user: User, project_id: UUID) -> list[ResearchNeed]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(ResearchNeed)
        .filter(ResearchNeed.project_id == project.id)
        .order_by(ResearchNeed.created_at.desc())
        .all()
    )


def update_statut(db: Session, user: User, project_id: UUID, need_id: UUID, statut: str) -> ResearchNeed:
    project = get_owned_project(db, user, project_id)
    need = (
        db.query(ResearchNeed)
        .filter(ResearchNeed.id == need_id, ResearchNeed.project_id == project.id)
        .first()
    )
    if need is None:
        raise ResearchNeedNotFoundError("Besoin introuvable.")

    need.statut = statut
    db.commit()
    db.refresh(need)
    return need
