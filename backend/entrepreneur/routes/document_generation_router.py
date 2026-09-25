"""Routes de la génération interactive de document (service 1.1.13 — pacte de
fondateurs ; réutilisable par 1.1.4/statuts via le même `document_type`, voir
document_generation_service.py).

GET  /projects/{id}/document-generation/{document_type} — état de la session
     (crée la session si absente) et de la section courante à afficher.
POST /projects/{id}/document-generation/{document_type}/sections/{code_section}
     — soumet la réponse pour la section courante.
POST /projects/{id}/document-generation/{document_type}/finalize — assemble
     et enregistre le document final (une fois `statut='complete'`).

Statuts (service 1.1.4, 24/09/2026) : garde-fou en deux niveaux --
`_run_regles_validite` (règles par code) puis `_run_guardrail_statuts` (LLM
ciblé sur les champs `controle_juridique`, non bloquant si le LLM est en
panne). Le pacte garde `_run_guardrail_on_free_text`.

Le garde-fou légal LLM (agents/contract_agent/legal_clause_guardrail_service.py)
est appelé ICI, avant document_generation_service.submit_section() — jamais
dans le service lui-même (agents/ = IA, backend/.../services = DB, même
séparation que document_service.py vs agents/shared/document_processing/).
Seules les variables de type 'texte' (saisie libre) passent par le garde-fou ;
les variables typées (nombre/montant/date/duree) et les références croisées
resolues automatiquement n'ont rien à juger sur le plan légal.

RETIRÉ (27/09/2026, service 1.1.15) : les endpoints .../sections/{code}/explain
et .../sections/answered — l'explication IA d'une clause (à la demande ou
automatique) est désormais UNIQUEMENT gérée par
backend/entrepreneur/routes/pacte_fondateur_copilot_router.py (voir sa
docstring pour la décision de consolidation : 3 mécanismes concurrents
construits successivement, un seul conservé). Ce fichier redevient
strictement "moteur de session" — plus de logique d'explication ici.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from agents.contract_agent.legal_clause_guardrail_service import LegalClauseGuardrailError, check_free_text
from agents.contract_agent.statuts_clause_guardrail_service import (
    check_statuts_section,
    construire_autres_valeurs,
    construire_champs,
)
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.schemas.document_generation_schemas import (
    DocumentGenerationSessionRead,
    FacultatifsChoixSubmit,
    GeneratedDocumentRead,
    PrevalidationRead,
    SectionAnswerSubmit,
    SectionStateRead,
    ValidationFinaleRead,
    CorrectionAppliqueeSubmit,
)
from backend.entrepreneur.services import document_generation_service as service
from backend.entrepreneur.services.document_generation_validation_service import valider_document
from backend.entrepreneur.services.statuts_sas_regles_validite import (
    GRAVITE_BLOQUANT,
    critere_verifiable_par_code,
    verifier_regles,
)
from backend.entrepreneur.services.statuts_sas_renderer import DOCUMENT_TYPE_STATUTS
from backend.entrepreneur.services.document_generation_service import (
    DocumentGenerationError,
    SectionNotFoundError,
    ValidationFinaleError,
)
from backend.entrepreneur.services.project_service import (
    ForbiddenError,
    ProjectError,
    ProjectNotFoundError,
    get_owned_project,
)
from backend.shared.auth.routes.auth_router import get_current_user
from backend.shared.database import get_db
from backend.shared.knowledge_base.services.clause_validity_criteria_service import list_for_clause
from backend.shared.models.user import User

router = APIRouter(prefix="/projects", tags=["entrepreneur-document-generation"])
logger = logging.getLogger(__name__)


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


@router.get("/{project_id}/document-generation/{document_type}/prevalidation", response_model=PrevalidationRead)
def get_prevalidation(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PrevalidationRead:
    # Appelée par le frontend au clic « Commencer » (statuts) : liste ce qui
    # manque dans le projet avant de pouvoir rédiger -- voir service.prevalider.
    try:
        return service.prevalider(db, current_user, project_id, document_type)
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


@router.post(
    "/{project_id}/document-generation/{document_type}/facultatifs",
    response_model=DocumentGenerationSessionRead,
)
def submit_facultatifs(
    project_id: UUID,
    document_type: str,
    body: FacultatifsChoixSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentGenerationSessionRead:
    """Choix des articles facultatifs sur l'écran de pause avant l'Art. 8
    (statuts, audit #19) — voir service.submit_facultatifs."""
    try:
        return service.submit_facultatifs(db, current_user, project_id, document_type, body.codes_choisis)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post(
    "/{project_id}/document-generation/{document_type}/facultatifs/retirer",
    response_model=DocumentGenerationSessionRead,
)
def retirer_facultatif(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentGenerationSessionRead:
    """Bouton "Ne plus inclure cet article" (statuts, audit #19) — voir
    service.retirer_facultatif_courant."""
    try:
        return service.retirer_facultatif_courant(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


def _noms_associes(db: Session, project_id: UUID) -> dict[str, str]:
    """{id: nom} des associés : pour nommer l'associé concerné quand une
    valeur est saisie par associé (apports en industrie)."""
    return {
        str(a_id): nom
        for a_id, nom in db.query(ProjectAssociate.id, ProjectAssociate.nom_complet).filter(
            ProjectAssociate.project_id == project_id
        )
    }


def _criteres_de(db: Session, clause) -> list[dict]:
    return [
        {"valeur_limite": c.valeur_limite, "base_legale": c.base_legale, "description_critere": c.description_critere}
        for c in list_for_clause(db, clause_library_id=clause.id)
    ]


def _run_regles_validite(
    db: Session, user: User, project_id: UUID, document_type: str, code_section: str, body: SectionAnswerSubmit
) -> None:
    """Niveau A du garde-fou (statuts uniquement, 24/09/2026) : critères de
    validité vérifiés PAR CODE sur les champs saisis (limites chiffrées,
    cohérence de délais…) -- voir statuts_sas_regles_validite.py. Passe
    AVANT le garde-fou LLM : un blocage certain n'a pas besoin d'un appel payant.

    Renvoie TOUS les problèmes en une fois (422). Des avertissements seuls
    bloquent aussi, sauf si `confirmer_avertissements` est vrai (l'utilisateur
    les a vus et continue)."""
    if document_type != DOCUMENT_TYPE_STATUTS or body.inclus is False:
        return
    # Propriété du projet vérifiée AVANT de lire ses associés (cette
    # vérification passe avant submit_section, qui fait aussi ce contrôle).
    get_owned_project(db, user, project_id)
    clause = service.resolve_target_clause(
        db, document_type, code_section, variante=body.variante, sous_variante=body.sous_variante
    )
    if clause is None:
        return
    problemes = verifier_regles(
        clause.variables_requises, _criteres_de(db, clause), body.valeurs, noms_associes=_noms_associes(db, project_id)
    )
    bloquants = [p for p in problemes if p["gravite"] == GRAVITE_BLOQUANT]
    if not bloquants and (not problemes or body.confirmer_avertissements):
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "message": (
                "Certaines valeurs ne respectent pas les règles des statuts."
                if bloquants
                else "Vérifiez ces points avant de continuer."
            ),
            "article_cite": None,
            "reformulation_proposee": None,
            "problemes": problemes,
            "avertissements_seulement": not bloquants,
        },
    )


def _run_guardrail_statuts(db: Session, project_id: UUID, code_section: str, body: SectionAnswerSubmit) -> list[str]:
    """Niveau B du garde-fou (statuts uniquement, 24/09/2026) : contrôle
    juridique LLM des seuls champs marqués `controle_juridique` dans le
    clausier (exceptions, motifs, majorités… -- pas une adresse ni un nom),
    en UN appel pour la section, avec le texte de la clause et les critères
    que le code ne vérifie pas (voir statuts_clause_guardrail_service.py).

    Refus -> 422 au même format que le niveau A (`problemes`), avec la
    reformulation proposée par champ.
    LLM indisponible -> on NE bloque PAS la saisie (un service externe en
    panne ne doit pas empêcher de rédiger) : renvoie les champs non vérifiés,
    notés dans la réponse de section pour la validation globale.
    Appelé après `_run_regles_validite` (qui a déjà vérifié la propriété du
    projet)."""
    if body.inclus is False:
        return []
    clause = service.resolve_target_clause(
        db, DOCUMENT_TYPE_STATUTS, code_section, variante=body.variante, sous_variante=body.sous_variante
    )
    if clause is None:
        return []
    if not any(v.get("controle_juridique") for v in clause.variables_requises):
        return []
    champs, cibles = construire_champs(clause.variables_requises, body.valeurs, _noms_associes(db, project_id))
    if not champs:
        return []
    autres_valeurs = construire_autres_valeurs(clause.variables_requises, body.valeurs)
    criteres = [c for c in _criteres_de(db, clause) if not critere_verifiable_par_code(c)]

    try:
        resultats = check_statuts_section(
            titre_clause=clause.titre_clause,
            texte_clause=clause.texte_clause,
            champs=champs,
            autres_valeurs=autres_valeurs,
            criteres=criteres,
        )
    except LegalClauseGuardrailError as exc:
        logger.warning("Garde-fou statuts indisponible (section %s), saisie acceptée à revérifier : %s", code_section, exc)
        return sorted({cibles[c["nom"]][0] for c in champs})

    problemes = [
        {
            "variable": cibles[nom][0],
            "associe_id": cibles[nom][2],
            "libelle": cibles[nom][1],
            "message": r.motif,
            "message_court": r.motif_court or "Formulation à revoir",
            "base_legale": r.article_cite,
            "gravite": GRAVITE_BLOQUANT,
            "reformulation_proposee": r.reformulation_proposee,
        }
        for nom, r in resultats.items()
        if not r.autorise
    ]
    if problemes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Certaines formulations posent un problème juridique.",
                "article_cite": None,
                "reformulation_proposee": None,
                "problemes": problemes,
                "avertissements_seulement": False,
            },
        )
    return []


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
        en_attente: list[str] = []
        if document_type == DOCUMENT_TYPE_STATUTS:
            # Statuts : règles par code (niveau A) puis LLM ciblé (niveau B).
            _run_regles_validite(db, current_user, project_id, document_type, code_section, body)
            en_attente = _run_guardrail_statuts(db, project_id, code_section, body)
        else:
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
            controle_juridique_en_attente=en_attente or None,
        )
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.get(
    "/{project_id}/document-generation/{document_type}/validation-finale", response_model=ValidationFinaleRead
)
def get_validation_finale(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ValidationFinaleRead:
    """Vérification finale avant génération (24/09/2026) : lance l'agent
    agents/document_generation_validation (tools dans l'ordre) et renvoie
    {pret, etapes, problemes}. Voir document_generation_validation_service."""
    try:
        return valider_document(db, current_user, project_id, document_type)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post(
    "/{project_id}/document-generation/{document_type}/sections/{code_section}/rouvrir",
    response_model=SectionStateRead,
)
def rouvrir_section(
    project_id: UUID,
    document_type: str,
    code_section: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionStateRead:
    """« Corriger → » depuis la vérification finale : rouvre une section sans
    effacer le reste du parcours — voir service.rouvrir_section."""
    try:
        return service.rouvrir_section(db, current_user, project_id, document_type, code_section)
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)


@router.post(
    "/{project_id}/document-generation/{document_type}/validation-finale/appliquer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def appliquer_correction(
    project_id: UUID,
    document_type: str,
    body: CorrectionAppliqueeSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """« Appliquer » une correction certaine proposée par la vérification
    finale (ex. somme déposée) — voir service.appliquer_correction."""
    try:
        service.appliquer_correction(
            db, current_user, project_id, document_type, body.code_section, body.variable, body.valeur
        )
    except (ProjectError, DocumentGenerationError) as exc:
        raise _handle_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/document-generation/{document_type}/correction/annuler", response_model=SectionStateRead)
def annuler_correction(
    project_id: UUID,
    document_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SectionStateRead:
    """« Revenir à la vérification » : annule la correction en cours."""
    try:
        return service.annuler_correction(db, current_user, project_id, document_type)
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
    except ValidationFinaleError as exc:
        # Vérification finale non passée : même contenu que …/validation-finale,
        # pour que le frontend réaffiche la liste sans deuxième appel.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": str(exc), "validation": exc.resultat},
        )
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
