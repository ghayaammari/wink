"""Routes du copilot pacte de fondateurs (service 1.1.13, categorie 3) --
bulle de discussion persistante, questions libres ou liees a une clause
(contexte de page).

POST /projects/{project_id}/pacte-fondateur-copilot/questions -- pose une
     question, cree la conversation si absente, renvoie la reponse + sources.
GET  /projects/{project_id}/pacte-fondateur-copilot/messages -- historique
     complet de la conversation (ajoute le 25/09/2026, voir
     pacte_fondateur_copilot_service.obtenir_historique pour le pourquoi).
POST /projects/{project_id}/pacte-fondateur-copilot/auto-explication --
     service 1.1.15 (27/09/2026) : pousse une explication automatique de la
     clause d'une section, appelee par le frontend a l'affichage de cette
     section (pas une question tapee par l'utilisateur). Seul mecanisme
     d'explication restant apres consolidation, voir
     pacte_fondateur_copilot_service.pousser_explication_section.

Meme pattern que document_generation_router.py (project_id en path, ownership
verifiee par project_service.get_owned_project via le service).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.pacte_fondateur_copilot_agent import PacteFondateurCopilotAgentError
from backend.entrepreneur.schemas.pacte_fondateur_copilot_schemas import (
    PacteFondateurAutoExplicationRead,
    PacteFondateurAutoExplicationRequest,
    PacteFondateurCopilotHistoryRead,
    PacteFondateurCopilotQuestion,
    PacteFondateurCopilotReponse,
)
from agents.agent_pacte_fondateur import pacte_fondateur_copilot_service as service
from agents.agent_pacte_fondateur.pacte_fondateur_copilot_service import PacteFondateurCopilotError
from backend.entrepreneur.services.document_generation_service import DocumentGenerationError, SectionNotFoundError
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-pacte-fondateur-copilot"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ProjectNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{project_id}/pacte-fondateur-copilot/questions",
    response_model=PacteFondateurCopilotReponse,
)
def poser_question(
    project_id: UUID,
    body: PacteFondateurCopilotQuestion,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PacteFondateurCopilotReponse:
    try:
        resultat = service.poser_question(
            db,
            current_user,
            project_id,
            question=body.question,
            code_clause_contexte=body.code_clause_contexte,
        )
    except (ProjectError,) as exc:
        raise _handle_error(exc)
    except PacteFondateurCopilotAgentError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Copilot indisponible, reessaie dans un instant : {exc}",
        )
    return PacteFondateurCopilotReponse(**resultat)


@router.get(
    "/{project_id}/pacte-fondateur-copilot/messages",
    response_model=PacteFondateurCopilotHistoryRead,
)
def obtenir_historique(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PacteFondateurCopilotHistoryRead:
    try:
        echanges = service.obtenir_historique(db, current_user, project_id)
    except (ProjectError,) as exc:
        raise _handle_error(exc)
    return PacteFondateurCopilotHistoryRead(echanges=echanges)


@router.post(
    "/{project_id}/pacte-fondateur-copilot/auto-explication",
    response_model=PacteFondateurAutoExplicationRead | None,
)
def pousser_explication_automatique(
    project_id: UUID,
    body: PacteFondateurAutoExplicationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PacteFondateurAutoExplicationRead | None:
    """Service 1.1.15 — appelee par le frontend a chaque nouvelle section
    affichee (voir PacteFondateurCopilotWidget.tsx), pas par une saisie
    utilisateur. Renvoie `null` (200, pas d'erreur) quand la section n'a pas
    de clause unique a expliquer -- cas normal (variante_obligatoire pas
    encore choisie, texte_statique, donnee_projet), pas une erreur cote
    frontend."""
    try:
        resultat = service.pousser_explication_section(
            db, current_user, project_id, document_type=body.document_type, code_section=body.code_section
        )
    except (ProjectError, SectionNotFoundError, DocumentGenerationError) as exc:
        raise _handle_error(exc)
    except PacteFondateurCopilotError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Explication automatique indisponible, reessaie dans un instant : {exc}",
        )
    if resultat is None:
        return None
    return PacteFondateurAutoExplicationRead(**resultat)
