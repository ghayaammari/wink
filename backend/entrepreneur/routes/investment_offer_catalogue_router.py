"""Route de lecture du catalogue des offres d'investissement ouvertes --

service 6.6.1 ("Feed de matching investisseurs"), étape de consultation
libre avant le matching. Fichier séparé de startup_offer_matching_router.py :
ce dernier est scopé à un project_id précis et déclenche/lit l'agent, alors
qu'ici il n'y a ni projet ni agent, juste un catalogue public en lecture
seule -- même distinction que investment_offer_router.py (CRUD investisseur)
vs investisseur_matching_router.py (matching) côté investisseur.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.entrepreneur.schemas.investment_offer_catalogue_schemas import OfferCatalogueRead
from backend.entrepreneur.services.investment_offer_catalogue_service import list_open_offers
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.models.user import User

router = APIRouter(prefix="/investissement/offres", tags=["entrepreneur-investissement-catalogue"])


@router.get("", response_model=list[OfferCatalogueRead])
def lister_catalogue_offres(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OfferCatalogueRead]:
    return list_open_offers(db)
