"""Logique métier du service 1.1.17 — coffre-fort documentaire. Groupe 4,
indépendant du copilot — voir docs/plan-implementation-groupe4.md.

Pure lecture, aucune nouvelle table : vue filtrée sur `documents`/
`document_versions` (déjà en base depuis I0, versionnement géré par
document_service.py au service 0.0.2 — un ré-upload crée une nouvelle ligne,
jamais d'écrasement). Le "service d'origine" d'un document se déduit de
`document_type`, jamais stocké séparément.

Fichier distinct de document_service.py (scopé au service 0.0.2, upload +
extraction) : responsabilité différente, même principe que
name_availability_service.py vs project_service.py.
"""
from uuid import UUID

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.schemas.document_vault_schemas import DocumentVaultItemRead, DocumentVersionRead
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service


class DocumentVaultError(Exception):
    """Erreur du coffre-fort documentaire (1.1.17) — base commune, voir sous-classes."""


class DocumentNotFoundError(DocumentVaultError):
    """Document ou version introuvable dans le projet demandé."""


class DocumentDownloadError(DocumentVaultError):
    """Échec de récupération des octets du fichier depuis Cloudinary."""


def list_project_documents(db: Session, user: User, project_id: UUID) -> list[DocumentVaultItemRead]:
    project = get_owned_project(db, user, project_id)

    # Sous-requête groupée plutôt qu'un COUNT() par document dans la boucle
    # Python (N+1) : une seule requête supplémentaire pour tous les documents
    # du projet, jointe comme les autres colonnes calculées ci-dessous.
    version_counts = (
        db.query(DocumentVersion.document_id, func.count(DocumentVersion.id).label("version_count"))
        .group_by(DocumentVersion.document_id)
        .subquery()
    )

    # outerjoin plutôt que join : current_version_id est nullable en base (voir
    # models/document.py) — un document sans version encore rattachée doit
    # quand même apparaître dans la liste, pas disparaître silencieusement.
    rows = (
        db.query(Document, DocumentVersion, version_counts.c.version_count)
        .outerjoin(DocumentVersion, Document.current_version_id == DocumentVersion.id)
        .outerjoin(version_counts, version_counts.c.document_id == Document.id)
        .filter(Document.project_id == project.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        DocumentVaultItemRead(
            id=document.id,
            document_type=document.document_type,
            original_filename=version.original_filename if version else None,
            mime_type=version.mime_type if version else None,
            size_bytes=version.size_bytes if version else None,
            created_at=document.created_at,
            # outerjoin -> None si aucune ligne document_versions pour ce document.
            version_count=version_count or 0,
        )
        for document, version, version_count in rows
    ]


def list_document_versions(db: Session, user: User, project_id: UUID, document_id: UUID) -> list[DocumentVersionRead]:
    """Historique complet d'un document (toutes les versions, y compris la
    courante — marquée `is_current`), plus récente en premier.
    """
    project = get_owned_project(db, user, project_id)

    document = db.query(Document).filter(Document.project_id == project.id, Document.id == document_id).first()
    if document is None:
        raise DocumentNotFoundError("Document introuvable.")

    versions = (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )

    return [
        DocumentVersionRead(
            id=version.id,
            version_number=version.version_number,
            original_filename=version.original_filename,
            mime_type=version.mime_type,
            size_bytes=version.size_bytes,
            created_at=version.created_at,
            is_current=version.id == document.current_version_id,
        )
        for version in versions
    ]


def _fetch_version_bytes(version: DocumentVersion) -> tuple[bytes, str, str]:
    """Récupère les octets d'une version précise depuis Cloudinary et les renvoie
    prêts à servir. Factorisé entre get_document_download() (version courante) et
    get_document_version_download() (version historique) : même logique réseau +
    gestion d'erreur, seul le DocumentVersion en entrée change — éviter de dupliquer
    le try/except requests ici aurait été le seul vrai risque de divergence.

    Utilise une URL signée régénérée depuis `cloudinary_public_id`, pas
    `version.secure_url` stockée en base : cette dernière est une URL non
    signée, bloquée en 401 par la restriction Cloudinary "Restricted media
    types" (raw/PDF publics interdits par défaut depuis avril 2024) — voir
    cloudinary_service.build_signed_raw_url().
    """
    url = cloudinary_service.build_signed_raw_url(version.cloudinary_public_id)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DocumentDownloadError(f"Échec de récupération du document depuis Cloudinary : {exc}") from exc

    filename = version.original_filename or "document"
    mime_type = version.mime_type or "application/octet-stream"
    return response.content, filename, mime_type


def get_document_download(db: Session, user: User, project_id: UUID, document_id: UUID) -> tuple[bytes, str, str]:
    """Retourne (contenu, nom de fichier, type MIME) pour la version COURANTE d'un
    document.

    Le backend récupère lui-même les octets depuis une URL signée régénérée
    (`requests.get`, sans transformation Cloudinary) puis les sert avec son
    propre header `Content-Disposition` (voir document_vault_router.py) —
    plutôt que d'exposer une URL Cloudinary au frontend et laisser le navigateur
    naviguer dessus directement. Deux raisons : (1) le flag Cloudinary
    `fl_attachment`, testé en premier pour forcer nom+extension au
    téléchargement, échoue en HTTP 400 sur ce compte (restriction Cloudinary
    sur les transformations de ressources `raw`, confirmé en conditions
    réelles) ; (2) même sans ce problème, cette route passe par
    `get_current_user`, donc `Authorization: Bearer`, ce qu'un lien `<a href>`
    direct vers Cloudinary ne peut pas porter.
    """
    project = get_owned_project(db, user, project_id)

    row = (
        db.query(Document, DocumentVersion)
        .outerjoin(DocumentVersion, Document.current_version_id == DocumentVersion.id)
        .filter(Document.project_id == project.id, Document.id == document_id)
        .first()
    )
    if row is None or row[1] is None:
        raise DocumentNotFoundError("Document introuvable ou sans fichier associé.")

    _document, version = row
    return _fetch_version_bytes(version)


def get_document_version_download(
    db: Session, user: User, project_id: UUID, document_id: UUID, version_id: UUID
) -> tuple[bytes, str, str]:
    """Comme get_document_download(), mais pour une version précise de l'historique
    (pas forcément la courante) — utilisé par le bouton de téléchargement de chaque
    ligne de l'historique côté frontend.
    """
    project = get_owned_project(db, user, project_id)

    version = (
        db.query(DocumentVersion)
        .join(Document, Document.id == DocumentVersion.document_id)
        .filter(
            Document.project_id == project.id,
            Document.id == document_id,
            DocumentVersion.id == version_id,
        )
        .first()
    )
    if version is None:
        raise DocumentNotFoundError("Version introuvable pour ce document.")

    return _fetch_version_bytes(version)
