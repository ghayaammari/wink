"""Logique métier du questionnaire d'onboarding — services 0.0.2, 0.0.3, 0.0.4.

Manipule `projects`, `project_legal_profiles`, `project_public_profiles` — voir
Wink_architecture_fichiers.md pour la justification du nom (par table/domaine,
pas par écran/flow).
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.models.project_public_profile import ProjectPublicProfile
from backend.entrepreneur.schemas.project_legal_profile_schemas import (
    ProjectLegalProfileCreate,
    ProjectLegalProfileUpdate,
)
from backend.entrepreneur.schemas.project_public_profile_schemas import ProjectPublicProfileUpdate
from backend.entrepreneur.schemas.project_schemas import ProjectUpdate
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service


class ProjectError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class ProjectNotFoundError(ProjectError):
    """Traduite en 404 — projet ou entrepreneur_profile introuvable."""


class ForbiddenError(ProjectError):
    """Traduite en 403 — le projet ciblé n'appartient pas à l'utilisateur connecté."""


# ---------------------------------------------------------------------------
# Résolution profil / autorisation — chaque fonction publique passe par ici
# ---------------------------------------------------------------------------

def get_entrepreneur_profile(db: Session, user: User) -> EntrepreneurProfile:
    profile = db.query(EntrepreneurProfile).filter(EntrepreneurProfile.user_id == user.id).first()
    if profile is None:
        # Ne devrait jamais arriver : auth_service crée ce profil automatiquement au signup
        # si role="entrepreneur". Un profil manquant signale une incohérence de données, pas
        # une erreur utilisateur normale.
        raise ProjectNotFoundError("Profil entrepreneur introuvable pour cet utilisateur.")
    return profile


def get_owned_project(db: Session, user: User, project_id) -> Project:
    """Vérifie authentification ET autorisation : le projet doit appartenir à

    l'entrepreneur_profile_id de l'utilisateur connecté, pas juste exister.
    Sans ce contrôle, un entrepreneur pourrait lire/modifier le projet d'un
    autre en devinant son UUID dans l'URL.
    """
    profile = get_entrepreneur_profile(db, user)
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise ProjectNotFoundError("Projet introuvable.")
    if project.entrepreneur_profile_id != profile.id:
        raise ForbiddenError("Ce projet ne t'appartient pas.")
    return project


# ---------------------------------------------------------------------------
# Complétion du profil — pourcentage calculé à la volée, statut binaire persisté
# ---------------------------------------------------------------------------

def _count_field(value, counters: dict) -> None:
    counters["total"] += 1
    if isinstance(value, list):
        if value:
            counters["filled"] += 1
    elif value not in (None, ""):
        counters["filled"] += 1


def _compute_completion(db: Session, project: Project) -> tuple[int, str]:
    """Retourne (pourcentage, statut) sans rien persister — à l'appelant de

    décider s'il committe `project.project_profile_completion`. 16 champs si
    project_type="created" (legal_name/siren inclus), 14 sinon — un écran sauté
    n'est pas compté comme manquant, il est retiré du calcul.
    """
    counters = {"filled": 0, "total": 0}

    for value in (
        project.project_type,
        project.stage,
        project.description,
        project.sector,
        project.subsectors,
        project.customer_segments,
        project.target_users,
        project.nombre_cofondateurs,
        project.intention_levee_fonds,
        project.technologies,
        project.value_proposition,
        project.localisation,
    ):
        _count_field(value, counters)

    if project.project_type == "created":
        legal_profile = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
        _count_field(legal_profile.legal_name if legal_profile else None, counters)
        _count_field(legal_profile.siren if legal_profile else None, counters)

    public_profile = db.query(ProjectPublicProfile).filter(ProjectPublicProfile.project_id == project.id).first()
    _count_field(public_profile.logo_url if public_profile else None, counters)
    _count_field(public_profile.website_url if public_profile else None, counters)

    percentage = round(counters["filled"] / counters["total"] * 100) if counters["total"] else 0
    status = "complet" if percentage == 100 else "incomplet"
    return percentage, status


def _attach_completion_percentage(db: Session, project: Project) -> None:
    """Pour une lecture (GET) : calcule et attache sans committer — un GET ne

    doit pas avoir d'effet de bord en base.
    """
    percentage, _status = _compute_completion(db, project)
    project.completion_percentage = percentage


def persist_completion(db: Session, project: Project) -> None:
    """Pour une écriture (POST/PATCH) : recalcule, persiste le statut binaire,

    et attache aussi le pourcentage pour la réponse — la transaction est de
    toute façon déjà committée par l'appelant juste après.
    """
    percentage, status = _compute_completion(db, project)
    project.project_profile_completion = status
    project.completion_percentage = percentage


# ---------------------------------------------------------------------------
# Écran 2 — Stade du projet
# ---------------------------------------------------------------------------

def create_project(db: Session, user: User, project_type: str, stage: str) -> Project:
    profile = get_entrepreneur_profile(db, user)

    existing = db.query(Project).filter(Project.entrepreneur_profile_id == profile.id).first()
    if existing is not None:
        # Restriction volontaire pour I0 : un seul projet actif par entrepreneur, même si
        # le modèle (entrepreneur_profile_id en FK simple, pas unique) autorise structurellement
        # plusieurs projets par entrepreneur pour un futur incrément.
        raise ProjectError("Un projet existe déjà pour ce compte.")

    project = Project(
        entrepreneur_profile_id=profile.id,
        project_type=project_type,
        stage=stage,
        description=None,
        source_type=None,
    )
    db.add(project)
    db.flush()
    persist_completion(db, project)
    db.commit()
    db.refresh(project)
    _attach_completion_percentage(db, project)
    return project


# ---------------------------------------------------------------------------
# Écran 3 — Informations légales (uniquement si project_type = created)
# ---------------------------------------------------------------------------

def create_legal_profile(
    db: Session, user: User, project_id, data: ProjectLegalProfileCreate
) -> ProjectLegalProfile:
    project = get_owned_project(db, user, project_id)

    if project.project_type != "created":
        raise ProjectError("Informations légales non applicables : le projet n'est pas encore immatriculé.")

    existing = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
    if existing is not None:
        raise ProjectError("Un profil légal existe déjà pour ce projet.")

    legal_profile = ProjectLegalProfile(project_id=project.id, **data.model_dump())
    db.add(legal_profile)
    persist_completion(db, project)
    db.commit()
    db.refresh(legal_profile)
    return legal_profile


def _verifier_coherence_capital(legal_profile: ProjectLegalProfile) -> None:
    """Capital = nombre d'actions × valeur nominale, contrôlé APRÈS fusion
    avec l'existant (un PATCH peut n'envoyer qu'un des 3 champs). Contrôle
    seulement si les 3 sont renseignés — un profil partiel reste accepté.
    Sans ce contrôle, les statuts (Art. 6/7) imprimeraient des montants
    contradictoires."""
    capital, actions, nominale = (
        legal_profile.capital_social,
        legal_profile.nombre_actions,
        legal_profile.valeur_nominale,
    )
    if capital is None or actions is None or nominale is None:
        return
    if Decimal(actions) * Decimal(nominale) != Decimal(capital):
        raise ProjectError(
            f"Incohérence : {actions} actions × {nominale} € = {Decimal(actions) * Decimal(nominale)} €, "
            f"différent du capital social ({capital} €)."
        )


def update_legal_profile(
    db: Session, user: User, project_id, data: ProjectLegalProfileUpdate
) -> ProjectLegalProfile:
    """PATCH /projects/{id}/legal-profile — upsert (contrairement à create_legal_profile

    ci-dessus, qui échoue si un profil existe déjà) : sert au bouton "Mettre à jour" de
    "Informations légales", appelable autant de fois que nécessaire. Les champs
    d'immatriculation (siren/siret/...) restent acceptés même si project_type != "created" ;
    c'est le frontend qui ne les envoie pas depuis le formulaire tant que la section est
    verrouillée (voir ProjectLegalInfoPage.tsx) — pas de contrôle bloquant ici, cohérent
    avec resolve_field_value qui accepte déjà ces champs via une candidate à tout moment.
    """
    project = get_owned_project(db, user, project_id)

    legal_profile = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
    if legal_profile is None:
        legal_profile = ProjectLegalProfile(project_id=project.id)
        db.add(legal_profile)
        db.flush()

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(legal_profile, field, value)
    _verifier_coherence_capital(legal_profile)

    persist_completion(db, project)
    db.commit()
    db.refresh(legal_profile)
    return legal_profile


# ---------------------------------------------------------------------------
# Écrans 4 à 8 — Présentation, questions contextuelles
# ---------------------------------------------------------------------------

def update_project(db: Session, user: User, project_id, data: ProjectUpdate) -> Project:
    project = get_owned_project(db, user, project_id)

    updates = data.model_dump(exclude_unset=True)
    # Pop avant le setattr loop : ce n'est pas une colonne de `projects`, c'est la
    # bookkeeping des champs extraits affichés sur cet écran (voir apply_resolutions).
    resolutions = updates.pop("resolved_field_values", None)
    for field, value in updates.items():
        setattr(project, field, value)

    # source_type fixé automatiquement au premier PATCH qui répond `description` (écran 4) —
    # jamais envoyé par le client dans ce parcours manuel (voir docstring ProjectUpdate).
    if "description" in updates and project.source_type is None:
        project.source_type = "texte_libre"

    if resolutions:
        # Import différé : document_service importe déjà project_service au niveau module
        # (get_owned_project, persist_completion) — un import en tête de fichier ici créerait
        # un cycle. Même transaction/commit que le PATCH principal (voir apply_resolutions).
        from backend.entrepreneur.services import document_service

        document_service.apply_resolutions(db, project, resolutions)

    persist_completion(db, project)
    db.commit()
    db.refresh(project)
    _attach_completion_percentage(db, project)
    return project


# ---------------------------------------------------------------------------
# Écran 9 — Vitrine publique (optionnel)
# ---------------------------------------------------------------------------

def upload_project_logo(db: Session, user: User, project_id, file_bytes: bytes) -> str:
    # get_owned_project sert ici uniquement de contrôle d'autorisation : on ne modifie
    # rien en base à cette étape, l'URL renvoyée est enregistrée par un appel séparé à
    # upsert_public_profile (même découpage que le plan d'implémentation Notion).
    get_owned_project(db, user, project_id)
    return cloudinary_service.upload_image(file_bytes)


def upsert_public_profile(
    db: Session, user: User, project_id, data: ProjectPublicProfileUpdate
) -> ProjectPublicProfile:
    project = get_owned_project(db, user, project_id)

    public_profile = db.query(ProjectPublicProfile).filter(ProjectPublicProfile.project_id == project.id).first()
    if public_profile is None:
        public_profile = ProjectPublicProfile(project_id=project.id)
        db.add(public_profile)

    updates = data.model_dump(exclude_unset=True)
    resolutions = updates.pop("resolved_field_values", None)
    for field, value in updates.items():
        setattr(public_profile, field, value)

    db.flush()

    if resolutions:
        from backend.entrepreneur.services import document_service

        document_service.apply_resolutions(db, project, resolutions)

    persist_completion(db, project)
    db.commit()
    db.refresh(public_profile)
    return public_profile


# ---------------------------------------------------------------------------
# Dashboard "Mon projet" — lecture seule des profils annexes
# ---------------------------------------------------------------------------

def get_legal_profile(db: Session, user: User, project_id) -> ProjectLegalProfile | None:
    """GET /projects/{id}/legal-profile. Retourne None plutôt qu'une 404 : un

    projet `project_type="created"` peut ne pas encore avoir de profil légal si
    l'entrepreneur n'a pas fini l'écran 3 (ex: accès direct au dashboard après
    onboarding partiel) — absence de profil légal est un état normal, pas une
    erreur, même logique que get_project_for_user pour `projects`.
    """
    project = get_owned_project(db, user, project_id)
    return db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()


def get_public_profile(db: Session, user: User, project_id) -> ProjectPublicProfile | None:
    """GET /projects/{id}/public-profile. Même raisonnement que get_legal_profile

    ci-dessus : l'écran 9 est facultatif (bouton "Passer"), l'absence de vitrine
    publique est un état normal.
    """
    project = get_owned_project(db, user, project_id)
    return db.query(ProjectPublicProfile).filter(ProjectPublicProfile.project_id == project.id).first()


# ---------------------------------------------------------------------------
# Écran 10 — Récapitulatif / routing post-login
# ---------------------------------------------------------------------------

def get_project_full(db: Session, user: User, project_id) -> Project:
    project = get_owned_project(db, user, project_id)
    _attach_completion_percentage(db, project)
    return project


def get_project_for_user(db: Session, user: User) -> Project | None:
    """GET /projects/me — utilisé par le frontend juste après login pour décider

    wizard vs accueil. Retourne None plutôt que de lever une erreur : l'absence
    de projet est un état normal, pas une erreur.
    """
    profile = get_entrepreneur_profile(db, user)
    project = db.query(Project).filter(Project.entrepreneur_profile_id == profile.id).first()
    if project is not None:
        _attach_completion_percentage(db, project)
    return project
