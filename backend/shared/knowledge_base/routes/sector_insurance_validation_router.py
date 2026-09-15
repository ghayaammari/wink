"""Endpoints du dashboard de validation humaine des recommandations d'assurance
sectorielles (service 1.1.10). Meme pattern que
`legal_texts_validation_router.py` : route et formate, toute logique DB dans
le service correspondant.

Securite : protege par `get_current_user` — meme dette technique assumee que
`legal_texts_validation_router.py` (pas de role admin).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.models.sector_insurance_recommendations import SectorInsuranceRecommendation
from backend.shared.knowledge_base.schemas.sector_insurance_schemas import (
    SectorInsuranceValidationAction,
    SectorInsuranceValidationItem,
)
from backend.shared.knowledge_base.services.sector_insurance_recommendations_service import (
    SectorInsuranceNotFoundError,
    list_pending_validation,
    validate_sector_insurance,
)
from backend.shared.models.user import User

router = APIRouter(
    prefix="/knowledge-base/sector-insurance", tags=["sector-insurance-validation"]
)


def _to_item(row: SectorInsuranceRecommendation) -> SectorInsuranceValidationItem:
    return SectorInsuranceValidationItem(
        id=row.id,
        secteur=row.secteur,
        type_assurance=row.type_assurance,
        a_base_legale=row.a_base_legale,
        source_nom=row.source_nom,
        source_url=row.source_url,
        texte_brut=row.texte_brut,
        longueur_caracteres=len(row.texte_brut) if row.texte_brut else 0,
    )


@router.get("/pending-validation", response_model=list[SectorInsuranceValidationItem])
def get_pending_validation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SectorInsuranceValidationItem]:
    return [_to_item(row) for row in list_pending_validation(db)]


@router.patch("/{record_id}/validation", response_model=SectorInsuranceValidationItem)
def patch_validation(
    record_id: uuid.UUID,
    body: SectorInsuranceValidationAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectorInsuranceValidationItem:
    try:
        row = validate_sector_insurance(db, record_id, body.action)
    except SectorInsuranceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    return _to_item(row)
