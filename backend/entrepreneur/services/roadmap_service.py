"""Logique métier du "Plan d'action pré-création" — suivi de progression sur

la roadmap `roadmap_nodes`/`startup_roadmap_items`, et dépôt de preuve
documentaire par étape. Service formalisé dans "Wink — Plan d'action
pré-création : spécification" (section 7), V1 uniquement (pas de copilot ni de
lancement direct de service EPIC-01 — V2/V3, hors périmètre ici).

Peuplement des `startup_roadmap_items` : tous les nœuds sont assignés dès le
premier accès — pas de filtrage à la création. Le filtrage par
`roadmap_nodes.applicable_if` se fait à l'affichage (service 1.1.11, voir
_evaluate_applicable_if).

Modification (réalisé par OPENCODE) : ajout du moteur d'évaluation
_evaluate_applicable_if et filtrage dans list_roadmap, puis implémentation de
la condition `droits_de_vote_dirigeants_foyer_fiscal_gt` (nœud
e21_immatriculation_fiscale) sur `project_associates` — la donnée source
existe désormais en base (migration e1b2c3d4e5f6, table socle du Groupe 5).
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.roadmap_node import RoadmapNode
from backend.entrepreneur.models.roadmap_node_dependency import RoadmapNodeDependency
from backend.entrepreneur.models.startup_roadmap_item import StartupRoadmapItem
from backend.entrepreneur.schemas.roadmap_schemas import RoadmapItemRead, RoadmapItemSettableStatut
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service

# Preuve documentaire par étape : pas seulement du PDF (contrairement à l'import
# de document 0.0.2, qui alimente un pipeline VLM) — une photo de Kbis ou de
# statuts signés est un cas d'usage réel ici. Pas d'extraction derrière, donc
# pas la même contrainte.
_ALLOWED_PROOF_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg"}

# États atteignables directement par une action utilisateur — voir
# RoadmapItemSettableStatut. "verrouille" est exclu : seul _cascade_unlock peut
# y toucher, sinon un client pourrait re-verrouiller une étape arbitrairement.
_SATISFYING_STATUTS = ("termine", "non_necessaire")


class RoadmapServiceError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class RoadmapItemNotFoundError(RoadmapServiceError):
    """Traduite en 404 — node_id inconnu de roadmap_nodes (ou hors de ce projet)."""


def _serialize_node(node: RoadmapNode) -> dict:
    """Copie figée écrite dans `node_snapshot` — texte descriptif uniquement.

    `groupe`/`ordre` ne sont PAS dupliqués ici : ce sont des méta-données
    structurelles lues en live depuis `roadmap_nodes` par `_read_item`, pas du
    contenu que l'entrepreneur "a vu" au sens du commentaire de node_snapshot.
    """
    return {
        "id": node.id,
        "nom": node.nom,
        "input": node.input,
        "description": node.description,
        "details_pratiques": node.details_pratiques,
        "administration_liee": node.administration_liee,
        "source_legale": node.source_legale,
        "bloquant": node.bloquant,
    }


def _evaluate_applicable_if(applicable_if: dict, project: Project, db: Session) -> bool:
    """Service 1.1.11 — évalue la condition `applicable_if` d'un nœud contre le
    profil réel du projet. Graphe vide = toujours applicable (réalisé par OPENCODE).
    """
    if not applicable_if:
        return True
    return all(_apply_condition(operator, operand, project, db) for operator, operand in applicable_if.items())


def _apply_condition(operator: str, operand, project: Project, db: Session) -> bool:
    """Application d'un opérateur de condition à la donnée projet disponible.

    Sélecteur inverse : tout opérateur inconnu à venir est évalué "toujours
    satisfait" — quand sa donnée existera, seul ce mapping évolue, pas
    l'architecture de filtrage. (réalisé par OPENCODE)
    """
    if operator == "nb_cofondateurs_gte":
        # Valeur non encore renseignée = on ne masque pas par défaut (fail-open).
        if project.nombre_cofondateurs is None:
            return True
        return project.nombre_cofondateurs >= operand
    if operator == "objectifs_immediats_contains":
        # Condition e23_depot_marque — ajouté avec la colonne projects.objectifs_immediats
        # (migration d5e6f7a8b9c1, question onboarding). Liste vide = non satisfaite.
        return operand in (project.objectifs_immediats or [])
    if operator == "droits_de_vote_dirigeants_foyer_fiscal_gt":
        # Condition e21_immatriculation_fiscale (art. 239 bis AB du CGI).
        # La somme porte sur les droits de vote des DIRIGEANTS ET de leur FOYER
        # FISCAL (conjoint/PACS/enfants à charge, art. 6 CGI) : les associés
        # est_dirigeant=true sont "chefs de foyer", et chaque associé rattaché à
        # un foyer (foyer_fiscal_dirigeant_associate_id non nul) compte aussi.
        # Droits de vote NULL = droits proportionnels au capital. Si aucune ligne
        # dirigeante (donnée pas encore saisie) = fail-open, on ne masque pas.
        votes = (
            db.query(func.coalesce(ProjectAssociate.pourcentage_droits_vote, ProjectAssociate.pourcentage_capital))
            .filter(
                ProjectAssociate.project_id == project.id,
                ProjectAssociate.est_dirigeant.is_(True),
            )
            .all()
        )
        if not votes:
            return True
        total = Decimal(sum(Decimal(str(vote or 0)) for (vote,) in votes))
        foyer = (
            db.query(func.coalesce(ProjectAssociate.pourcentage_droits_vote, ProjectAssociate.pourcentage_capital))
            .filter(
                ProjectAssociate.project_id == project.id,
                ProjectAssociate.foyer_fiscal_dirigeant_associate_id.is_not(None),
                ProjectAssociate.est_dirigeant.is_(False),
            )
            .all()
        )
        for (vote,) in foyer:
            total += Decimal(str(vote or 0))
        return total > Decimal(str(operand))
    return True


def _get_item(db: Session, project_id, node_id: str) -> StartupRoadmapItem | None:
    return (
        db.query(StartupRoadmapItem)
        .filter(StartupRoadmapItem.project_id == project_id, StartupRoadmapItem.node_id == node_id)
        .first()
    )


def _dependencies(db: Session, node_id: str) -> list[str]:
    return [
        row.depends_on_node_id
        for row in db.query(RoadmapNodeDependency).filter(RoadmapNodeDependency.node_id == node_id)
    ]


def _dependents(db: Session, node_id: str) -> list[str]:
    return [
        row.node_id
        for row in db.query(RoadmapNodeDependency).filter(RoadmapNodeDependency.depends_on_node_id == node_id)
    ]


def _dependencies_map(db: Session, node_ids: list[str]) -> dict[str, list[str]]:
    """Version groupée de `_dependencies` pour list_roadmap — une seule requête

    pour les ~24 nœuds du projet plutôt qu'une par nœud (même logique de
    N+1 que _base_item_query pour les jointures).
    """
    result: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    rows = db.query(RoadmapNodeDependency).filter(RoadmapNodeDependency.node_id.in_(node_ids))
    for row in rows:
        result[row.node_id].append(row.depends_on_node_id)
    return result


def _is_satisfied(db: Session, project_id, node_id: str) -> bool:
    """Un nœud sans dépendance est satisfait par défaut (vrai vide) — c'est ce

    qui fait démarrer les nœuds racines à `a_faire` dès leur création, sans cas
    particulier séparé dans _ensure_items.
    """
    deps = _dependencies(db, node_id)
    if not deps:
        return True
    satisfied_count = (
        db.query(StartupRoadmapItem)
        .filter(
            StartupRoadmapItem.project_id == project_id,
            StartupRoadmapItem.node_id.in_(deps),
            StartupRoadmapItem.statut.in_(_SATISFYING_STATUTS),
        )
        .count()
    )
    return satisfied_count == len(deps)


def _cascade_unlock(db: Session, project_id, node_id: str) -> None:
    """Propage le déverrouillage aux nœuds qui dépendent de `node_id`, après que

    celui-ci vient de passer à un statut satisfaisant (termine/non_necessaire).
    Récursif : déverrouiller un nœud peut à son tour en déverrouiller d'autres
    plus loin dans le graphe. Pas de protection anti-cycle ici : déjà garantie
    à l'écriture par seed_roadmap_nodes._validate_graph (le graphe est un DAG).
    """
    for dependent_id in _dependents(db, node_id):
        item = _get_item(db, project_id, dependent_id)
        if item is not None and item.statut == "verrouille" and _is_satisfied(db, project_id, dependent_id):
            item.statut = "a_faire"
            db.flush()
            _cascade_unlock(db, project_id, dependent_id)


def _ensure_items(db: Session, project_id) -> None:
    existing_node_ids = {
        row[0] for row in db.query(StartupRoadmapItem.node_id).filter(StartupRoadmapItem.project_id == project_id)
    }
    nodes = db.query(RoadmapNode).all()
    new_nodes = [n for n in nodes if n.id not in existing_node_ids]
    if not new_nodes:
        return

    # Remarque : deux requêtes concurrentes au tout premier accès du même projet
    # pourraient toutes deux tenter de créer les mêmes lignes et se heurter à
    # `uq_startup_roadmap_items_project_node`. Non géré ici (pas de retry/upsert)
    # — même niveau de robustesse que le reste du service (aucune autre route
    # entrepreneur ne gère ce genre de course), pas une régression introduite ici.
    for node in new_nodes:
        db.add(StartupRoadmapItem(project_id=project_id, node_id=node.id, node_snapshot=_serialize_node(node)))
    db.flush()  # les lignes doivent exister avant que _is_satisfied puisse les compter

    for node in new_nodes:
        if _is_satisfied(db, project_id, node.id):
            item = _get_item(db, project_id, node.id)
            item.statut = "a_faire"
    db.commit()


def _base_item_query(db: Session):
    """Requête de base, jointures communes à _read_item et list_roadmap — un

    seul endroit à faire évoluer si une colonne supplémentaire est un jour
    nécessaire côté lecture.
    """
    return (
        db.query(StartupRoadmapItem, DocumentVersion.secure_url, RoadmapNode.groupe, RoadmapNode.ordre, RoadmapNode.applicable_if)
        .join(RoadmapNode, RoadmapNode.id == StartupRoadmapItem.node_id)
        .outerjoin(Document, Document.id == StartupRoadmapItem.proof_document_id)
        .outerjoin(DocumentVersion, DocumentVersion.id == Document.current_version_id)
    )


def _row_to_read(row, depends_on: list[str]) -> RoadmapItemRead:
    item, proof_url, groupe, ordre, _applicable_if = row
    return RoadmapItemRead(
        id=item.id,
        project_id=item.project_id,
        node_id=item.node_id,
        groupe=groupe,
        ordre=ordre,
        statut=item.statut,
        node_snapshot=item.node_snapshot,
        depends_on=depends_on,
        proof_document_id=item.proof_document_id,
        proof_document_url=proof_url,
        assigned_at=item.assigned_at,
        completed_at=item.completed_at,
    )


def _read_item(db: Session, project_id, node_id: str) -> RoadmapItemRead | None:
    row = (
        _base_item_query(db)
        .filter(StartupRoadmapItem.project_id == project_id, StartupRoadmapItem.node_id == node_id)
        .first()
    )
    if row is None:
        return None
    return _row_to_read(row, _dependencies(db, node_id))


def list_roadmap(db: Session, user: User, project_id: UUID) -> list[RoadmapItemRead]:
    project = get_owned_project(db, user, project_id)
    _ensure_items(db, project.id)

    # Une seule requête avec jointures plutôt qu'une boucle _read_item par
    # nœud (24 requêtes + 24 sous-requêtes) — évite le N+1 évident ici.
    rows = (
        _base_item_query(db)
        .filter(StartupRoadmapItem.project_id == project.id)
        .order_by(RoadmapNode.ordre)
        .all()
    )
    # Service 1.1.11 — filtrage à l'affichage : un nœud n'est affiché que si sa
    # condition applicable_if est satisfaite par le profil courant du projet.
    # Le statut ne rentre pas en compte (un nœud en_cours/termine devenu
    # inapplicable est aussi masqué, conformément à la décision de cadrage).
    # (réalisé par OPENCODE)
    rows = [row for row in rows if _evaluate_applicable_if(row[4], project, db)]
    deps_map = _dependencies_map(db, [item.node_id for item, *_rest in rows])
    return [_row_to_read(row, deps_map[row[0].node_id]) for row in rows]


def update_status(
    db: Session, user: User, project_id: UUID, node_id: str, statut: RoadmapItemSettableStatut
) -> RoadmapItemRead:
    project = get_owned_project(db, user, project_id)
    _ensure_items(db, project.id)

    item = _get_item(db, project.id, node_id)
    if item is None:
        raise RoadmapItemNotFoundError(f"Étape '{node_id}' introuvable.")

    # Cocher une étape "déjà réalisée" est autorisé même si elle est encore
    # `verrouille` (cas réel : un entrepreneur qui a commencé ses démarches
    # avant d'utiliser Wink) — voir "Plan d'action pré-création : spécification",
    # comportement n°1, aucune condition de déblocage mentionnée.
    item.statut = statut
    item.completed_at = datetime.now(timezone.utc) if statut == "termine" else None
    db.flush()

    if statut in _SATISFYING_STATUTS:
        _cascade_unlock(db, project.id, node_id)

    db.commit()
    return _read_item(db, project.id, node_id)


def attach_proof(
    db: Session,
    user: User,
    project_id: UUID,
    node_id: str,
    file_bytes: bytes,
    filename: str,
    mime_type: str | None,
) -> RoadmapItemRead:
    project = get_owned_project(db, user, project_id)
    _ensure_items(db, project.id)

    item = _get_item(db, project.id, node_id)
    if item is None:
        raise RoadmapItemNotFoundError(f"Étape '{node_id}' introuvable.")

    if mime_type not in _ALLOWED_PROOF_MIME_TYPES:
        raise RoadmapServiceError("Seuls les fichiers PDF, PNG ou JPEG sont acceptés comme preuve.")

    # Même logique que document_service.upload_and_extract : nouvelle version si
    # une preuve existe déjà pour cette étape (préserve l'historique), sinon
    # premier upload.
    if item.proof_document_id is not None:
        document = db.query(Document).filter(Document.id == item.proof_document_id).first()
        last_version = (
            db.query(DocumentVersion.version_number)
            .filter(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        next_version_number = (last_version[0] if last_version else 0) + 1
    else:
        document = Document(owner_user_id=user.id, project_id=project.id, document_type="other")
        db.add(document)
        db.flush()
        next_version_number = 1

    cloudinary_result = cloudinary_service.upload_raw_file(file_bytes, folder="wink/roadmap-proofs")

    version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_number,
        original_filename=filename,
        cloudinary_public_id=cloudinary_result["public_id"],
        secure_url=cloudinary_result["secure_url"],
        mime_type=mime_type,
        size_bytes=len(file_bytes),
    )
    db.add(version)
    db.flush()

    document.current_version_id = version.id
    item.proof_document_id = document.id

    db.commit()
    return _read_item(db, project.id, node_id)
