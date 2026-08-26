"""Logique métier de l'import de document — upload, extraction automatique, et
résolution (confirmer/corriger/ignorer) des `project_field_values`. Service 0.0.2,
volet "import de document".

`field_value` est toujours stocké en JSON (`json.dumps`), même pour un texte
simple (ex: `"Paris"` stocké comme `"\"Paris\""`) : les champs extraits couvrent
plusieurs types Python (str, int, bool, list), et json.dumps/json.loads donne un
round-trip fiable vers la vraie colonne sans maintenir une table de correspondance
champ → type Python séparée de `_TABLE_MODELS`. À prendre en compte côté frontend
(Phase 3/4) : envoyer/lire `field_value` comme du JSON, pas du texte brut.
"""

import json

from sqlalchemy.orm import Session

from agents.shared.document_processing.service import DocumentProcessingError, extract_document
from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_field_value import ProjectFieldValue
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.models.project_public_profile import ProjectPublicProfile
from backend.entrepreneur.schemas.project_field_value_schemas import ProjectFieldValueUpdate
from backend.entrepreneur.services.project_service import get_owned_project, persist_completion
from backend.shared.models.user import User
from backend.shared.services import cloudinary_service


class DocumentServiceError(Exception):
    """Erreur métier générique — traduite en 400 par défaut dans le router."""


class DocumentNotFoundError(DocumentServiceError):
    """Traduite en 404 — champ extrait introuvable ou n'appartenant pas au projet."""


# PDF uniquement pour l'instant — voir agents/shared/document_processing/vlm_extraction/vlm_service.py
_ALLOWED_MIME_TYPES = {"application/pdf"}

# Préfixe "table.colonne" dans field_name (ex: "projects.sector") pour lever
# l'ambiguïté entre tables qui partagent un nom de champ (sector, technologies
# existent à la fois dans projects et project_public_profiles).
_TABLE_MODELS = {
    "projects": Project,
    "project_legal_profiles": ProjectLegalProfile,
    "project_public_profiles": ProjectPublicProfile,
}


def _get_or_create_profile_row(db: Session, model, project_id):
    """project_legal_profiles / project_public_profiles n'existent peut-être pas

    encore (créées seulement quand l'utilisateur atteint l'écran correspondant
    du questionnaire) — upsert plutôt qu'update pour ne pas échouer si l'écran
    n'a pas encore été vu au moment où un champ extrait est confirmé.
    """
    row = db.query(model).filter(model.project_id == project_id).first()
    if row is None:
        row = model(project_id=project_id)
        db.add(row)
        db.flush()
    return row


def upload_and_extract(
    db: Session, user: User, project_id, file_bytes: bytes, filename: str, mime_type: str | None
) -> list[ProjectFieldValue]:
    project = get_owned_project(db, user, project_id)

    if mime_type not in _ALLOWED_MIME_TYPES:
        raise DocumentServiceError("Seuls les fichiers PDF sont acceptés pour l'instant.")

    # 1. Document + DocumentVersion — nouvelle version si un document est déjà associé
    # au projet (préserve l'historique, voir document_versions), sinon premier upload.
    if project.imported_document_id is not None:
        document = db.query(Document).filter(Document.id == project.imported_document_id).first()
        last_version = (
            db.query(DocumentVersion.version_number)
            .filter(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        next_version_number = (last_version[0] if last_version else 0) + 1
    else:
        document = Document(owner_user_id=user.id, project_id=project.id, document_type="entrepreneur_idea")
        db.add(document)
        db.flush()
        next_version_number = 1

    cloudinary_result = cloudinary_service.upload_raw_file(file_bytes, folder="wink/documents")

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
    project.imported_document_id = document.id
    project.source_type = "document_importe"

    # 2. Extraction — échec partiel possible (ex: 2 des 3 appels LLM réussissent, le 3e
    # lève). On garde le document/la version déjà committés (l'upload a réussi) plutôt
    # que de tout annuler, et on remonte l'erreur pour information côté frontend.
    try:
        extracted = extract_document(file_bytes, schema_name="entrepreneur_project")
    except DocumentProcessingError as exc:
        db.commit()
        raise DocumentServiceError(f"Document importé, mais échec de l'extraction : {exc}") from exc

    # 3. project_field_values — upsert (UniqueConstraint project_id+field_name gère les
    # ré-extractions sur un document déjà importé une fois).
    field_values: list[ProjectFieldValue] = []
    for table_name, fields in extracted.items():
        for column, value in fields.items():
            if value in (None, [], ""):
                continue
            field_name = f"{table_name}.{column}"
            field_value = (
                db.query(ProjectFieldValue)
                .filter(ProjectFieldValue.project_id == project.id, ProjectFieldValue.field_name == field_name)
                .first()
            )
            if field_value is None:
                field_value = ProjectFieldValue(project_id=project.id, field_name=field_name)
                db.add(field_value)
            field_value.field_value = json.dumps(value)
            field_value.extraction_source = "extrait_automatique"
            field_value.validation_status = "en_attente"
            field_values.append(field_value)

    db.commit()
    for fv in field_values:
        db.refresh(fv)
    return field_values


def list_field_values(db: Session, user: User, project_id) -> list[ProjectFieldValue]:
    project = get_owned_project(db, user, project_id)
    return db.query(ProjectFieldValue).filter(ProjectFieldValue.project_id == project.id).all()


def _get_owned_field_value(db: Session, user: User, project_id, field_value_id) -> ProjectFieldValue:
    project = get_owned_project(db, user, project_id)
    field_value = (
        db.query(ProjectFieldValue)
        .filter(ProjectFieldValue.id == field_value_id, ProjectFieldValue.project_id == project.id)
        .first()
    )
    if field_value is None:
        raise DocumentNotFoundError("Champ extrait introuvable.")
    return field_value


def resolve_field_value(
    db: Session, user: User, project_id, field_value_id, data: ProjectFieldValueUpdate
) -> ProjectFieldValue:
    """Confirmer ou corriger un champ extrait : écrit la valeur dans la vraie

    colonne cible (projects / project_legal_profiles / project_public_profiles),
    puis met à jour project_field_values pour la traçabilité.
    """
    field_value = _get_owned_field_value(db, user, project_id, field_value_id)
    project = get_owned_project(db, user, project_id)

    table_name, column = field_value.field_name.split(".", 1)
    model = _TABLE_MODELS.get(table_name)
    if model is None:
        raise DocumentServiceError(f"Table cible inconnue pour le champ {field_value.field_name!r}.")

    # Si le client n'envoie pas de field_value (cas "confirmer" : la valeur extraite est
    # déjà correcte), on réécrit la valeur déjà stockée plutôt que d'exiger qu'il la
    # renvoie telle quelle.
    final_raw_value = data.field_value if data.field_value is not None else field_value.field_value
    final_value = json.loads(final_raw_value) if final_raw_value is not None else None

    target_row = project if model is Project else _get_or_create_profile_row(db, model, project.id)
    setattr(target_row, column, final_value)

    field_value.field_value = final_raw_value
    field_value.validation_status = data.validation_status

    persist_completion(db, project)
    db.commit()
    db.refresh(field_value)
    return field_value


def ignore_field_value(db: Session, user: User, project_id, field_value_id) -> None:
    field_value = _get_owned_field_value(db, user, project_id, field_value_id)
    db.delete(field_value)
    db.commit()


def apply_resolutions(db: Session, project: Project, resolutions: list[dict]) -> None:
    """Bookkeeping `project_field_values` pour la "confirmation globale" (écrans 4-9) :

    appelée par project_service.update_project / upsert_public_profile, dans la MÊME
    transaction que le PATCH principal. Ne touche PAS aux colonnes réelles (projects /
    project_public_profiles / ...) — la valeur est déjà appliquée par l'appelant via son
    propre setattr loop, dans le même payload. Ici on fait uniquement : validation_status
    pour confirme/corrige, suppression de la ligne pour ignore (pas de trace d'audit
    voulue pour "ignoré", même comportement que ignore_field_value ci-dessus).

    Pas de commit ici : c'est l'appelant qui committe la transaction globale.
    """
    for resolution in resolutions:
        field_value = (
            db.query(ProjectFieldValue)
            .filter(ProjectFieldValue.id == resolution["id"], ProjectFieldValue.project_id == project.id)
            .first()
        )
        if field_value is None:
            # Déjà résolu/supprimé (double-clic, re-soumission) — idempotent, pas une erreur.
            continue
        if resolution["action"] == "ignore":
            db.delete(field_value)
        else:
            field_value.validation_status = resolution["action"]
