"""Routes du service pitch deck (6.6.2) — profil dedie, generation, lecture

du dernier deck, telechargement PPTX. Fichier distinct de project_router.py :
responsabilite differente, voir Wink_architecture_fichiers.md.

Regeneration explicite (POST .../pitch/generate), jamais automatique -- meme
convention que .../ai-act/diagnostic (ai_act_router.py) : un appel LLM ne se
declenche jamais silencieusement derriere un simple GET ou PATCH de profil.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.pitch_deck_agent.deck_schema import DeckContentModel
from agents.pitch_deck_agent.pitch_deck_content_service import PitchDeckAgentError
from backend.entrepreneur.schemas.pitch_schemas import ProjectPitchProfileRead, ProjectPitchProfileUpdate
from backend.entrepreneur.services import pitch_deck_service, pitch_profile_service
from backend.entrepreneur.services.pitch_deck_service import PitchDeckNotFoundError
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-pitch"])


def _handle_pitch_error(exc: Exception) -> HTTPException:
    """Meme principe que _handle_ai_act_error (ai_act_router.py)."""
    if isinstance(exc, (ProjectNotFoundError, PitchDeckNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, PitchDeckAgentError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/pitch/profile", response_model=ProjectPitchProfileRead)
def get_pitch_profile(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPitchProfileRead:
    try:
        return pitch_profile_service.get_or_create_profile(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_pitch_error(exc)


@router.patch("/{project_id}/pitch/profile", response_model=ProjectPitchProfileRead)
def update_pitch_profile(
    project_id: UUID,
    body: ProjectPitchProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPitchProfileRead:
    try:
        return pitch_profile_service.update_profile(db, current_user, project_id, body)
    except ProjectError as exc:
        raise _handle_pitch_error(exc)


@router.post("/{project_id}/pitch/generate", response_model=DeckContentModel)
def generate_pitch_deck(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckContentModel:
    try:
        return pitch_deck_service.generate_deck(db, current_user, project_id)
    except (ProjectError, PitchDeckAgentError) as exc:
        raise _handle_pitch_error(exc)


@router.get("/{project_id}/pitch", response_model=DeckContentModel)
def get_pitch_deck(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeckContentModel:
    try:
        return pitch_deck_service.get_latest_deck(db, current_user, project_id)
    except (ProjectError, PitchDeckNotFoundError) as exc:
        raise _handle_pitch_error(exc)


@router.get("/{project_id}/pitch/file")
def get_pitch_deck_file(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        pptx_bytes = pitch_deck_service.get_pptx_bytes(db, current_user, project_id)
    except (ProjectError, PitchDeckNotFoundError) as exc:
        raise _handle_pitch_error(exc)
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": "attachment; filename=pitch-deck.pptx"},
    )
