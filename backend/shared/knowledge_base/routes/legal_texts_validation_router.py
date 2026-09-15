"""Endpoints du dashboard de validation humaine (Phase 1.5, service 1.1.1 —
Étapes 1.5.2/1.5.3 du plan Notion). Ce fichier ne fait que router et formater
la réponse (longueur_caracteres, nb_alineas_detectes, Étape 1.5.1) ; toute la
logique DB vit dans legal_texts_service.py — voir cette règle appliquée
partout ailleurs (routes/ appelle services/, jamais l'inverse).

Sécurité : protégé seulement par `get_current_user` (n'importe quel compte
connecté), faute de rôle "admin" dans le système actuel — dette technique
assumée. À resserrer (restriction à un rôle admin) si ce dashboard devient
accessible à autre chose qu'un usage interne/dev.
"""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.models.legal_texts import LegalText
from backend.shared.knowledge_base.schemas.legal_texts_schemas import (
    LegalTextValidationAction,
    LegalTextValidationItem,
)
from backend.shared.knowledge_base.services.legal_texts_service import (
    LegalTextNotFoundError,
    list_pending_validation,
    validate_legal_text,
)
from backend.shared.models.user import User

router = APIRouter(prefix="/knowledge-base/legal-texts", tags=["legal-texts-validation"])

# Sépare sur double saut de ligne ou numérotation "1°"/"2°"/"3°" en début
# d'alinéa — indicatif seulement (plan Notion : "pas fiable à 100%"), jamais
# utilisé pour une décision automatique, juste affiché en petit dans le
# dashboard.
_ALINEA_SEPARATOR = re.compile(r"\n\s*\n|(?:^|\n)\s*\d+°")


def _to_item(row: LegalText) -> LegalTextValidationItem:
    parts = [p for p in _ALINEA_SEPARATOR.split(row.texte_brut) if p.strip()]
    return LegalTextValidationItem(
        id=row.id,
        article_numero=row.article_numero,
        forme_juridique_concernee=row.forme_juridique_concernee,
        texte_brut=row.texte_brut,
        chunking_suggere=row.chunking_suggere,
        longueur_caracteres=len(row.texte_brut),
        nb_alineas_detectes=max(len(parts), 1),
    )


@router.get("/pending-validation", response_model=list[LegalTextValidationItem])
def get_pending_validation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LegalTextValidationItem]:
    return [_to_item(row) for row in list_pending_validation(db)]


@router.patch("/{legal_text_id}/validation", response_model=LegalTextValidationItem)
def patch_validation(
    legal_text_id: uuid.UUID,
    body: LegalTextValidationAction,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LegalTextValidationItem:
    try:
        row = validate_legal_text(db, legal_text_id, body.action)
    except LegalTextNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    db.commit()
    return _to_item(row)
