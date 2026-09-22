"""Routes de la génération interactive de document (service 1.1.13 — pacte de
fondateurs ; réutilisable par 1.1.4/statuts via le même `document_type`, voir
document_generation_service.py).

GET  /projects/{id}/document-generation/{document_type} — état de la session
     (crée la session si absente) et de la section courante à afficher.
POST /projects/{id}/document-generation/{document_type}/sections/{code_section}
     — soumet la réponse pour la section courante.
POST /projects/{id}/document-generation/{document_type}/finalize — assemble
     et enregistre le document final (une fois `statut='complete'`).

Le garde-fou légal LLM (agents/contract_agent/legal_clause_guardrail_service.py)
est appelé ICI, avant document_generation_service.submit_section() — jamais
dans le service lui-même (agents/ = IA, backend/.../services = DB, même
séparation que document_service.py vs agents/shared/document_processing/).
Seules les variables de type 'texte' (saisie libre) passent par le garde-fou ;
les variables typées (nombre/montant/date/duree) et les références croisées
resolues automatiquement n'ont rien à juger sur le plan légal.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.contract_agent.legal_clause_guardrail_service import LegalClauseGuardrailError, check_free_text
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.schemas.document_generation_schemas import (
    DocumentGenerationSessionRead,
    GeneratedDocumentRead,
    SectionAnswerSubmit,
    SectionStateRead,
)
from backend.entrepreneur.services import document_generation_service as service
from backend.entrepreneur.services.document_generation_service import (
    DocumentGenerationError,
    SectionNotFoundError,
)
from backend.entrepreneur.services.project_service import ForbiddenError, ProjectError, ProjectNotFoundError
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.services.clause_validity_criteria_service import list_for_clause
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-document-generation"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ProjectNotFoundError, SectionNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ForbiddenError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{project_id}/document-generation/{document_type}/preview")
def get_document_preview(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Preview PDF de la session en cours (v2 -- rédaction article par article,
    voir PacteFondateursV2Page.tsx) : streamée à chaque appel, jamais stockée
    (option B tranchée avec l'utilisateur, 21/09/2026) -- pas de
    `response_model` Pydantic ici, la réponse est directement le flux binaire
    du PDF, pas du JSON.
    """
    try:
        pdf_bytes = service.get_document_preview_pdf(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/{project_id}/document-generation/{document_type}", response_model=SectionStateRead)
def get_current_section(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionStateRead:
    try:
        return service.get_current_section_state(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/document-generation/{document_type}/back", response_model=SectionStateRead)
def go_back(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionStateRead:
    """Revient à la dernière section interactive répondue (bouton "Précédent"
    du formulaire, 24/09/2026) — voir service.go_to_previous_section."""
    try:
        return service.go_to_previous_section(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/document-generation/{document_type}/restart", response_model=SectionStateRead)
def restart(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionStateRead:
    """Repart de zéro sur la session existante (24/09/2026) — voir
    service.restart_session pour pourquoi une session unique par
    (projet, document_type) empêchait sinon de recréer un pacte après en
    avoir déjà finalisé un."""
    try:
        return service.restart_session(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


def _run_guardrail_on_free_text(db: Session, document_type: str, code_section: str, body: SectionAnswerSubmit) -> None:
    """Vérifie chaque variable de type 'texte' soumise, AVANT que submit_section
    ne les persiste. Lève 422 si le LLM bloque le texte — le motif et la
    reformulation proposée sont renvoyés au frontend pour que l'utilisateur
    puisse corriger sans deviner pourquoi c'est refusé.
    """
    clause = service.resolve_target_clause(
        db, document_type, code_section, variante=body.variante, sous_variante=body.sous_variante
    )
    if clause is None:
        return

    texte_variables = {v["nom"] for v in clause.variables_requises if v["type"] == "texte"}
    if not texte_variables:
        return

    criteres = [
        {
            "description_critere": c.description_critere,
            "valeur_limite": c.valeur_limite,
            "base_legale": c.base_legale,
        }
        for c in list_for_clause(db, clause_library_id=clause.id)
    ]

    for nom in texte_variables:
        valeur = body.valeurs.get(nom)
        if not valeur:
            continue
        try:
            result = check_free_text(str(valeur), contexte=clause.titre_clause, criteres=criteres)
        except LegalClauseGuardrailError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Vérification légale indisponible, réessaie dans un instant : {exc}",
            )
        if not result.autorise:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": f"Texte refusé pour '{nom}' : {result.motif}",
                    "article_cite": result.article_cite,
                    "reformulation_proposee": result.reformulation_proposee,
                },
            )


@router.post(
    "/{project_id}/document-generation/{document_type}/sections/{code_section}",
    response_model=DocumentGenerationSessionRead,
)
def submit_section(
    project_id: UUID,
    document_type: str,
    code_section: str,
    body: SectionAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentGenerationSessionRead:
    try:
        _run_guardrail_on_free_text(db, document_type, code_section, body)
        return service.submit_section(
            db,
            current_user,
            project_id,
            document_type,
            code_section,
            inclus=body.inclus,
            variante=body.variante,
            sous_variante=body.sous_variante,
            valeurs=body.valeurs,
        )
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post("/{project_id}/document-generation/{document_type}/finalize", response_model=GeneratedDocumentRead)
def finalize(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GeneratedDocumentRead:
    try:
        document = service.finalize_session(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)

    # Document n'a pas de relationship ORM vers sa version courante (seulement
    # current_version_id, voir models/document.py — FK circulaire, use_alter) :
    # une requête explicite plutôt qu'un attribut qui n'existe pas sur le modèle.
    version = db.get(DocumentVersion, document.current_version_id)
    return GeneratedDocumentRead(
        document_id=document.id,
        document_type=document.document_type,
        secure_url=version.secure_url if version else "",
        original_filename=version.original_filename if version else "",
    )
