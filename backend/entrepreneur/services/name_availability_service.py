"""Logique métier du service 1.1.2 — vérificateur croisé de disponibilité du
nom (dénomination sociale + marque). Groupe 4, indépendant du copilot — voir
page Notion "Schemas grp 4".

Chaque vérification insère une nouvelle ligne dans `name_availability_checks`
(jamais un update) : un entrepreneur peut tester plusieurs noms avant de se
décider, l'historique complet reste consultable.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.name_availability_check import NameAvailabilityCheck
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User
from scrapers.inpi.marques_client import InpiApiError, search_marque_status
from scrapers.recherche_entreprises.client import RechercheEntreprisesApiError, is_active_match, search_by_name
from scrapers.shared.text_normalize import fold


class NameAvailabilityServiceError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class NameAvailabilityUpstreamError(NameAvailabilityServiceError):
    """Échec d'un appel externe (API indisponible, identifiants INPI manquants...) —
    traduite en 503 : ce n'est pas une erreur de l'utilisateur, mais on ne peut
    pas répondre tant que la source externe ne répond pas.
    """


def _check_denomination(nom: str) -> str:
    try:
        results = search_by_name(nom)
    except RechercheEntreprisesApiError as exc:
        raise NameAvailabilityUpstreamError(f"Vérification de dénomination indisponible : {exc}") from exc
    return "pris" if is_active_match(results, fold(nom)) else "disponible"


def _check_marque(nom: str) -> str:
    try:
        return search_marque_status(nom)
    except InpiApiError as exc:
        raise NameAvailabilityUpstreamError(f"Vérification de marque indisponible : {exc}") from exc


def check_name_availability(db: Session, user: User, project_id: UUID, nom_teste: str) -> NameAvailabilityCheck:
    project = get_owned_project(db, user, project_id)

    # Les 2 vérifications sont indépendantes (2 API distinctes) mais la ligne
    # `name_availability_checks` exige les 2 statuts (NOT NULL) — si l'une des
    # 2 échoue, on n'insère rien de partiel/faux plutôt que d'afficher un statut
    # inventé. Voir NameAvailabilityUpstreamError -> 503 côté route.
    statut_denomination = _check_denomination(nom_teste)
    statut_marque = _check_marque(nom_teste)

    check = NameAvailabilityCheck(
        project_id=project.id,
        nom_teste=nom_teste,
        statut_denomination=statut_denomination,
        statut_marque=statut_marque,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def list_name_availability_checks(db: Session, user: User, project_id: UUID) -> list[NameAvailabilityCheck]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(NameAvailabilityCheck)
        .filter(NameAvailabilityCheck.project_id == project.id)
        .order_by(NameAvailabilityCheck.verifie_le.desc())
        .all()
    )
