"""Dashboard de validation humaine de `jal_reference` (service 1.1.5). Même
pattern que `legal_texts_validation_router.py` : route et formate, toute la
logique DB dans le service.

Sécurité : `get_current_user` seulement — même dette assumée que les autres
dashboards de validation (pas de rôle admin dans le système).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.schemas.jal_reference_schemas import (
    JalReferenceValidationAction,
    JalReferenceValidationItem,
)
from backend.shared.knowledge_base.services.jal_reference_service import (
    JalReferenceNotFoundError,
    list_pending_validation,
    validate_jal,
)
from backend.shared.models.user import User

router = APIRouter(prefix="/knowledge-base/jal-reference", tags=["jal-reference-validation"])


@router.get("/pending-validation", response_model=list[JalReferenceValidationItem])
def get_pending(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list_pending_validation(db)


@router.patch("/{jal_id}/validation", response_model=JalReferenceValidationItem)
def patch_validation(
    jal_id: uuid.UUID,
    body: JalReferenceValidationAction,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    try:
        ligne = validate_jal(db, jal_id, body.type_support)
    except JalReferenceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    db.refresh(ligne)
    return ligne
