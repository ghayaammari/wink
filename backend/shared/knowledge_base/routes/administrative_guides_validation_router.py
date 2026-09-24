"""Endpoints du dashboard de validation humaine de `administrative_guides` —
meme convention que `legal_texts_validation_router.py` (routes/ appelle
services/, jamais l'inverse).

Securite : protege seulement par `get_current_user`, meme dette technique
assumee que `legal_texts_validation_router.py` (pas de role "admin" dans le
systeme actuel).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.models.administrative_guides import AdministrativeGuide
from backend.shared.knowledge_base.schemas.administrative_guides_schemas import AdministrativeGuideValidationItem
from backend.shared.knowledge_base.services.administrative_guides_service import (
    AdministrativeGuideNotFoundError,
    list_pending_validation,
    validate_administrative_guide,
)
from backend.shared.models.user import User

router = APIRouter(prefix="/knowledge-base/administrative-guides", tags=["administrative-guides-validation"])


def _to_item(row: AdministrativeGuide) -> AdministrativeGuideValidationItem:
    return AdministrativeGuideValidationItem(
        id=row.id,
        domaine=row.domaine,
        source_nom=row.source_nom,
        source_url=row.source_url,
        titre=row.titre,
        texte_brut=row.texte_brut,
        longueur_caracteres=len(row.texte_brut),
    )


@router.get("/pending-validation", response_model=list[AdministrativeGuideValidationItem])
def get_pending_validation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AdministrativeGuideValidationItem]:
    return [_to_item(row) for row in list_pending_validation(db)]


@router.patch("/{guide_id}/validation", response_model=AdministrativeGuideValidationItem)
def patch_validation(
    guide_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AdministrativeGuideValidationItem:
    try:
        row = validate_administrative_guide(db, guide_id)
    except AdministrativeGuideNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    return _to_item(row)
