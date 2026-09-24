"""Logique métier de la page "Équipe & capital" — liste réelle des associés.

Stocke `project_associates` (répartition du capital / droits de vote), socle des
services 1.1.13 (pacte), 1.1.4 (statuts) et 1.1.6 (DBE) — voir Groupe5_doc.md.

Modèle d'édition "brouillon + enregistrement global" (décision de conception) :
- les opérations unitaires (create/update/delete) ne valident QUE les règles de
  forme (apport en industrie hors capital, dirigeant avec fonction, pas de
  suppression du représentant légal). Elles peuvent laisser la répartition dans
  un état intermédiaire (somme ≠ 100 %) — c'est le brouillon.
- `replace_associates` (PUT, la liste COMPLÈTE envoyée au clic "Enregistrer")
  valide l'état cible : somme des parts de capital = exactement 100 % ET au
  moins un dirigeant, puis applique atomiquement. C'est ici que vit la règle
  bloquante "somme = 100 %" — un changement isolé (ex: réduire le fondateur de
  100 % à 90 %) ne peut donc pas se retrouver piégé dans un état invalide.
- la ligne du fondateur (associé = propriétaire du projet, `linked_user_id`
  renseigné) est créée automatiquement à la lecture de la page si absente :
  identité connue depuis I0, répartition 100 % solo par défaut.

Réutilise ProjectError/ProjectNotFoundError/ForbiddenError et
get_owned_project de project_service (mêmes traductions HTTP dans le router).
(réalisé par OPENCODE)
"""
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.schemas.project_associate_schemas import (
    ProjectAssociateBatchItem,
    ProjectAssociateCreate,
    ProjectAssociateUpdate,
)
from backend.entrepreneur.services.project_service import (
    ProjectError,
    ProjectNotFoundError,
    get_owned_project,
)
from backend.shared.models.user import User

# Pourcentage cible : parts de capital, 2 décimales (0,01 px). La somme
# d'arrondi maximale (99,999999909…) est tolérée via ces écarts.
_CAPITAL_CENT = Decimal("100")
_TOLERANCE = Decimal("0.011")


def _compose_founder_name(user: User) -> str:
    parts = [p for p in (user.first_name, user.last_name) if p]
    if parts:
        return " ".join(parts)
    # Fallback : `users` n'impose pas de nom (nullable) — on garde l'email pour
    # satisfaire le NOT NULL, l'entrepreneur corrigera son nom dans la page.
    return user.email or "Fondateur"


def ensure_founder_associate(db: Session, user: User, project_id) -> ProjectAssociate | None:
    """SI la ligne du fondateur n'existe pas encore, la crée (100 % solo, dirigeant).

    Appelée en tête de chaque lecture de la page ("Équipe & capital") : c'est
    l'accès à la page qui matérialise la ligne, pas la création du projet —
    il n'y a aucune autre source du nom de l'associé que `users`.
    """
    project = get_owned_project(db, user, project_id)

    founder = (
        db.query(ProjectAssociate)
        .filter(
            ProjectAssociate.project_id == project.id,
            ProjectAssociate.linked_user_id == user.id,
        )
        .first()
    )
    if founder is not None:
        return founder

    founder = ProjectAssociate(
        project_id=project.id,
        nom_complet=_compose_founder_name(user),
        type_personne="personne_physique",
        pourcentage_capital=_CAPITAL_CENT,
        pourcentage_droits_vote=None,
        type_apport="numeraire",
        est_dirigeant=True,
        fonction_dirigeant="Président",
        est_partie_au_pacte_fondateurs=False,
        # La ligne auto-créée ici EST celle du fondateur du projet (voir
        # docstring de cette fonction) — `est_fondateur=True` par défaut pour
        # que si l'utilisateur coche ensuite "Membre du pacte de fondateurs",
        # il apparaisse dans les Associés Fondateurs et pas dans les
        # Associés Investisseurs (incohérence trouvée le 24/09/2026 : le nom
        # de la fonction et ces autres valeurs par défaut le traitent déjà
        # comme le fondateur, mais ce booléen restait à False). Reste
        # modifiable ensuite (Équipe & capital ou l'écran de sélection du
        # pacte v2), au cas où l'entrepreneur ne se considère pas fondateur
        # pour ce pacte précis.
        est_fondateur=True,
        linked_user_id=user.id,
    )
    db.add(founder)
    db.commit()
    db.refresh(founder)
    return founder


def _total_from_items(items: list[ProjectAssociateBatchItem]) -> Decimal:
    return sum((i.pourcentage_capital for i in items), Decimal("0"))


def _validate_target(items: list[ProjectAssociateBatchItem]) -> None:
    """RÈGLE BLOQUANTE au clic "Enregistrer" (PUT /associates) : sur l'état cible
    de la liste complète, la somme des parts de capital vaut exactement 100 % et
    au moins un associé est dirigeant. Vérifiée AVANT toute écriture, pour
    qu'une liste incohérente ne soit jamais persistée.
    """
    total = _total_from_items(items)
    if total < _CAPITAL_CENT - _TOLERANCE or total > _CAPITAL_CENT + _TOLERANCE:
        raise ProjectError(f"La somme des parts de capital doit être de 100 % (actuellement {total:.2f} %).")
    if not any(i.est_dirigeant for i in items):
        raise ProjectError("Au moins un associé doit être dirigeant.")


def _validate_foyer_target(db: Session, project_id, foyer_associate_id) -> None:
    """Le foyer fiscal d'un associé doit référencer un DIRIGEANT du même projet.

    NULL = non rattaché (cas par défaut). Vérifié pour les opérations unitaires
    (brouillon) comme pour le PUT global — voir condition e21 (art. 239 bis AB
    du CGI, roadmap_service). (réalisé par OPENCODE)
    """
    if foyer_associate_id is None:
        return
    target = (
        db.query(ProjectAssociate)
        .filter(
            ProjectAssociate.id == foyer_associate_id,
            ProjectAssociate.project_id == project_id,
        )
        .first()
    )
    if target is None:
        raise ProjectError("Le foyer fiscal doit référencer un associé de ce projet.")
    if not target.est_dirigeant:
        raise ProjectError("Le foyer fiscal doit référencer un associé dirigeant (le chef de foyer).")


def _validate_dirigeant_not_in_foyer(est_dirigeant: bool, foyer_associate_id) -> None:
    """Un dirigeant est "chef de foyer" — il ne peut pas être rattaché à un autre."""
    if est_dirigeant and foyer_associate_id is not None:
        raise ProjectError("Un dirigeant ne peut pas être rattaché au foyer fiscal d'un autre associé.")


def get_associate(db: Session, user: User, project_id, associate_id) -> ProjectAssociate:
    """Résolution + contrôle d'appartenance d'un associé (404 si inconnu ou d'un autre projet)."""
    project = get_owned_project(db, user, project_id)
    associate = (
        db.query(ProjectAssociate)
        .filter(
            ProjectAssociate.id == associate_id,
            ProjectAssociate.project_id == project.id,
        )
        .first()
    )
    if associate is None:
        raise ProjectNotFoundError("Associé introuvable pour ce projet.")
    return associate


def list_associates(db: Session, user: User, project_id) -> list[ProjectAssociate]:
    project = get_owned_project(db, user, project_id)
    ensure_founder_associate(db, user, project.id)
    return (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project.id)
        .order_by(ProjectAssociate.created_at)
        .all()
    )


def create_associate(db: Session, user: User, project_id, data: ProjectAssociateCreate) -> ProjectAssociate:
    """Brouillon — n'applique pas la règle des 100 % (voir docstring module)."""
    project = get_owned_project(db, user, project_id)

    if data.type_apport == "industrie" and data.pourcentage_capital != 0:
        raise ProjectError("Un apport en industrie ne concourt jamais au capital (art. 1843-2).")
    if data.est_dirigeant and not data.fonction_dirigeant:
        raise ProjectError("Un dirigeant doit avoir une fonction renseignée.")
    _validate_dirigeant_not_in_foyer(data.est_dirigeant, data.foyer_fiscal_dirigeant_associate_id)
    _validate_foyer_target(db, project.id, data.foyer_fiscal_dirigeant_associate_id)

    associate = ProjectAssociate(project_id=project.id, **data.model_dump())
    db.add(associate)
    db.commit()
    db.refresh(associate)
    return associate


def update_associate(
    db: Session, user: User, project_id, associate_id, data: ProjectAssociateUpdate
) -> ProjectAssociate:
    """Brouillon — n'applique pas la règle des 100 % (voir docstring module)."""
    associate = get_associate(db, user, project_id, associate_id)

    updates = data.model_dump(exclude_unset=True)

    type_apport = updates.get("type_apport", associate.type_apport)
    capital = updates.get("pourcentage_capital", associate.pourcentage_capital)
    if type_apport == "industrie" and capital != 0:
        raise ProjectError("Un apport en industrie ne concourt jamais au capital (art. 1843-2).")

    dirigeant = updates.get("est_dirigeant", associate.est_dirigeant)
    fonction = updates.get("fonction_dirigeant", associate.fonction_dirigeant)
    if dirigeant and not fonction:
        raise ProjectError("Un dirigeant doit avoir une fonction renseignée.")

    foyer = updates.get("foyer_fiscal_dirigeant_associate_id", associate.foyer_fiscal_dirigeant_associate_id)
    _validate_dirigeant_not_in_foyer(dirigeant, foyer)
    _validate_foyer_target(db, associate.project_id, foyer)

    for field, value in updates.items():
        setattr(associate, field, value)

    db.commit()
    db.refresh(associate)
    return associate


def delete_associate(db: Session, user: User, project_id, associate_id) -> None:
    """Brouillon — n'applique pas la règle des 100 % (voir docstring module).

    Garde une règle d'intégrité : l'associé désigné représentant légal ne peut
    pas être supprimé individuellement ici (le responsable doit d'abord le
    changer dans le profil légal / statuts).
    """
    associate = get_associate(db, user, project_id, associate_id)

    is_rep = (
        db.query(ProjectLegalProfile)
        .filter(
            ProjectLegalProfile.project_id == project_id,
            ProjectLegalProfile.legal_representative_associate_id == associate.id,
        )
        .first()
    )
    if is_rep is not None:
        raise ProjectError("Cet associé est le représentant légal — désignez-en un autre avant de le supprimer.")

    db.delete(associate)
    db.commit()


def replace_associates(
    db: Session, user: User, project_id, items: list[ProjectAssociateBatchItem]
) -> list[ProjectAssociate]:
    """PUT /projects/{id}/associates — enregistrement GLOBAL de la page.

    Reçoit la liste complète des associés (id présent = mise à jour d'une ligne
    existante, id absent = création). Valide la règle bloquante (somme = 100 %,
    ≥ 1 dirigeant) sur l'état cible AVANT d'écrire, supprime les lignes absentes
    de la liste, puis committe atomiquement.
    """
    project = get_owned_project(db, user, project_id)

    directed = {it.id for it in items if it.id is not None}
    existing_rows = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == project.id)
        .all()
    )
    existing = {a.id: a for a in existing_rows}

    # Le représentant légal ne peut pas sortir de la liste au passage d'un PUT.
    removed_ids = set(existing.keys()) - directed
    if removed_ids:
        is_rep = (
            db.query(ProjectLegalProfile)
            .filter(
                ProjectLegalProfile.project_id == project.id,
                ProjectLegalProfile.legal_representative_associate_id.in_(removed_ids),
            )
            .first()
        )
        if is_rep is not None:
            raise ProjectError(
                "Associé est le représentant légal — désignez-en un autre avant de l'enregistrer hors de la liste."
            )

    _validate_target(items)

    result: list[ProjectAssociate] = []
    for item in items:
        dump = item.model_dump(exclude={"id"})
        if item.id is not None and item.id in existing:
            target = existing[item.id]
            for field, value in dump.items():
                setattr(target, field, value)
        else:
            target = ProjectAssociate(project_id=project.id, id=item.id, **dump)
            db.add(target)
        result.append(target)

    # Cohérence du foyer fiscal sur l'état cible COMPLET (nouvelles lignes incluses,
    # dirigeants pouvant être redésignés par le même PUT) : la cible doit être une
    # ligne dirigeante du même projet, et un dirigeant ne peut pas être rattaché.
    target_by_id = {a.id: a for a in result if a.id is not None}
    for target in result:
        foyer = target.foyer_fiscal_dirigeant_associate_id
        if foyer is not None:
            _validate_dirigeant_not_in_foyer(target.est_dirigeant, foyer)
            chef = target_by_id.get(foyer)
            if chef is None or not chef.est_dirigeant:
                raise ProjectError("Le foyer fiscal doit référencer un associé dirigeant de cette liste.")

    for rid in removed_ids:
        db.delete(existing[rid])

    db.commit()
    for target in result:
        db.refresh(target)
    return result