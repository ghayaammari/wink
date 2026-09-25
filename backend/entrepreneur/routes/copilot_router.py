"""Routes du copilot conformite -- conversations (CRUD minimal) et envoi de

message dans une conversation. Fichier distinct des autres routers
(rgpd_router.py, ai_act_router.py...) : responsabilite differente
(conversation libre, pas un diagnostic d'un domaine precis), voir
Wink_architecture_fichiers.md.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.orchestrator.copilot_agent_service import CopilotAgentError
from backend.entrepreneur.schemas.copilot_schemas import (
    CopilotConversationDetail,
    CopilotConversationSummary,
    CopilotMessageRequest,
    CopilotMessageResponse,
)
from backend.entrepreneur.services.copilot_service import (
    CopilotConversationError,
    CopilotConversationNotFoundError,
    create_conversation,
    get_conversation,
    list_conversations,
    send_message,
)
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-copilot"])
logger = logging.getLogger(__name__)


def _handle_copilot_error(exc: Exception) -> HTTPException:
    """Meme principe que _handle_rgpd_error (rgpd_router.py)."""
    if isinstance(exc, (ProjectNotFoundError, CopilotConversationNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, CopilotAgentError):
        # Loggee ici (pas seulement renvoyee au client) : un 502 signifie que
        # l'appel LLM a echoue cote Groq/LangGraph, ce n'est jamais attendu
        # en usage normal -- sans ce log, la cause reelle (corps d'erreur
        # Groq, ex. schema de structured output rejete) n'apparaissait nulle
        # part cote serveur, seulement dans le corps de la reponse HTTP.
        logger.exception("Echec de l'agent copilot : %s", exc)
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{project_id}/copilot/conversations",
    response_model=CopilotConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def creer_conversation_copilot(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CopilotConversationSummary:
    try:
        return create_conversation(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_copilot_error(exc)


@router.get("/{project_id}/copilot/conversations", response_model=list[CopilotConversationSummary])
def lister_conversations_copilot(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CopilotConversationSummary]:
    try:
        return list_conversations(db, current_user, project_id)
    except ProjectError as exc:
        raise _handle_copilot_error(exc)


@router.get(
    "/{project_id}/copilot/conversations/{conversation_id}", response_model=CopilotConversationDetail
)
def lire_conversation_copilot(
    project_id: UUID,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CopilotConversationDetail:
    try:
        return get_conversation(db, current_user, project_id, conversation_id)
    except (ProjectError, CopilotConversationError) as exc:
        raise _handle_copilot_error(exc)


@router.post(
    "/{project_id}/copilot/conversations/{conversation_id}/message", response_model=CopilotMessageResponse
)
def envoyer_message_copilot(
    project_id: UUID,
    conversation_id: UUID,
    body: CopilotMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CopilotMessageResponse:
    try:
        return send_message(db, current_user, project_id, conversation_id, body.content, body.tronquer_a)
    except (ProjectError, CopilotConversationError, CopilotAgentError) as exc:
        raise _handle_copilot_error(exc)
