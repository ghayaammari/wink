"""Dashboard de validation humaine de `legal_announcement_guides` (service
1.1.5, copilot). Même pattern et même dette (pas de rôle admin) que
`legal_texts_validation_router.py`."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.schemas.legal_announcement_guides_schemas import (
    LegalAnnouncementGuideValidationItem,
)
from backend.shared.knowledge_base.services.legal_announcement_guides_service import (
    LegalAnnouncementGuideNotFoundError,
    list_pending_validation,
    validate_guide,
)
from backend.shared.models.user import User

router = APIRouter(
    prefix="/knowledge-base/legal-announcement-guides", tags=["legal-announcement-guides-validation"]
)


@router.get("/pending-validation", response_model=list[LegalAnnouncementGuideValidationItem])
def get_pending(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return list_pending_validation(db)


@router.patch("/{guide_id}/validation", response_model=LegalAnnouncementGuideValidationItem)
def patch_validation(guide_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        ligne = validate_guide(db, guide_id)
    except LegalAnnouncementGuideNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    db.refresh(ligne)
    return ligne
