"""Logique métier de `company_officers` — dirigeants désignés dans les statuts
SAS (service 1.1.4, lot 5 du 24/09/2026).

Avant ce fichier, la table existait (modèle + schémas) mais RIEN ne
l'écrivait : Président, Directeur Général, membres du comité et mandataire
sortaient en « (non renseigné) » dans les statuts (Art. 39-41, 44, Annexe III).

Une action = un enregistrement (ajouter / modifier / supprimer UN dirigeant),
contrairement à "Équipe & capital" (PUT global) : aucune règle ne porte sur
l'ensemble de la liste (pas d'équivalent de « somme des parts = 100 % »),
chaque dirigeant se valide seul. Toutes les règles sont vérifiées sur l'état
FINAL de la ligne (`_preparer`), en création comme en modification.
"""
from sqlalchemy.orm import Session

from backend.entrepreneur.models.company_officer import CompanyOfficer
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.schemas.company_officer_schemas import CompanyOfficerCreate, CompanyOfficerUpdate
from backend.entrepreneur.services.project_service import ProjectError, ProjectNotFoundError, get_owned_project
from backend.shared.models.user import User

# Rôles à titulaire UNIQUE : les clauses ne lisent que « le » Président, « le »
# premier Directeur Général et « le » mandataire (voir `_premier_officier` dans
# statuts_sas_resolvers.py). Un 2e titulaire serait silencieusement ignoré au
# rendu -- refusé ici plutôt que perdu. `membre_comite` reste multiple.
_ROLES_UNIQUES = {
    "president": "Président",
    "directeur_general": "Directeur Général",
    "mandataire": "mandataire pour les actes avant immatriculation",
}

# Champs d'identité propres à `company_officers`, vidés quand le dirigeant est
# un associé : son identité vit alors dans `project_associates`
# (anti-redondance, voir docstring du modèle). `representant_nom`/`_prenom`
# sont GARDÉS : le représentant permanent d'une personne morale est propre au
# MANDAT, il n'existe pas sur `project_associates`.
_CHAMPS_IDENTITE_HORS_ASSOCIE = (
    "nom_complet",
    "denomination_sociale",
    "forme_juridique",
    "capital_social",
    "siege_social",
    "lieu_immatriculation",
    "siren",
    "adresse",
)


def list_officers(db: Session, user: User, project_id) -> list[CompanyOfficer]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(CompanyOfficer)
        .filter(CompanyOfficer.project_id == project.id)
        .order_by(CompanyOfficer.created_at)
        .all()
    )


def _get_owned_officer(db: Session, project_id, officer_id) -> CompanyOfficer:
    officer = (
        db.query(CompanyOfficer)
        .filter(CompanyOfficer.id == officer_id, CompanyOfficer.project_id == project_id)
        .first()
    )
    if officer is None:
        # Même réponse qu'un dirigeant d'un autre projet : on ne révèle pas
        # son existence.
        raise ProjectNotFoundError("Dirigeant introuvable.")
    return officer


def _preparer(db: Session, project_id, officer: CompanyOfficer) -> None:
    """Valide et normalise l'état FINAL d'une ligne avant écriture."""
    if officer.associate_id is not None:
        associe = (
            db.query(ProjectAssociate)
            .filter(ProjectAssociate.id == officer.associate_id, ProjectAssociate.project_id == project_id)
            .first()
        )
        if associe is None:
            raise ProjectError("Le dirigeant choisi n'est pas un associé de ce projet.")
        # Le type de personne suit celui de l'associé (source de vérité), et
        # son identité n'est jamais dupliquée ici.
        officer.type_personne = associe.type_personne
        for champ in _CHAMPS_IDENTITE_HORS_ASSOCIE:
            setattr(officer, champ, None)
    elif officer.type_personne == "personne_morale":
        if not (officer.denomination_sociale or "").strip():
            raise ProjectError("Indiquez la dénomination de la société dirigeante.")
    elif not (officer.nom_complet or "").strip():
        raise ProjectError("Indiquez le nom du dirigeant.")

    if officer.role in _ROLES_UNIQUES:
        doublon = (
            db.query(CompanyOfficer)
            .filter(
                CompanyOfficer.project_id == project_id,
                CompanyOfficer.role == officer.role,
                CompanyOfficer.id != officer.id if officer.id is not None else True,
            )
            .first()
        )
        if doublon is not None:
            raise ProjectError(f"Un {_ROLES_UNIQUES[officer.role]} est déjà désigné : modifiez-le plutôt que d'en ajouter un 2e.")


def create_officer(db: Session, user: User, project_id, data: CompanyOfficerCreate) -> CompanyOfficer:
    project = get_owned_project(db, user, project_id)
    officer = CompanyOfficer(project_id=project.id, **data.model_dump())
    _preparer(db, project.id, officer)
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return officer


def update_officer(
    db: Session, user: User, project_id, officer_id, data: CompanyOfficerUpdate
) -> CompanyOfficer:
    project = get_owned_project(db, user, project_id)
    officer = _get_owned_officer(db, project.id, officer_id)
    for champ, valeur in data.model_dump(exclude_unset=True).items():
        setattr(officer, champ, valeur)
    # `no_autoflush` : la requête d'unicité de `_preparer` ne doit pas écrire
    # la ligne modifiée avant sa validation.
    with db.no_autoflush:
        _preparer(db, project.id, officer)
    db.commit()
    db.refresh(officer)
    return officer


def delete_officer(db: Session, user: User, project_id, officer_id) -> None:
    project = get_owned_project(db, user, project_id)
    officer = _get_owned_officer(db, project.id, officer_id)
    db.delete(officer)
    db.commit()
