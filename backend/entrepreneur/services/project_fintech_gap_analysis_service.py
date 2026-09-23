"""Logique métier de `project_fintech_gap_analysis` — service 3.3.6, volet

FinTech. Beaucoup plus simple que son équivalent HealthTech (pas de
chapitres, pas de verrouillage) : juste une lecture (résultat généré ou non)
et une persistance. Voir fintech_gap_analysis_diagnostic_service.py pour
l'orchestration RAG + agent.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_fintech_gap_analysis import ProjectFintechGapAnalysis
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.services.fintech_data_profile_service import (
    get_or_create_profile as get_or_create_fintech_profile,
    is_profile_complete as is_fintech_profile_complete,
)
from backend.entrepreneur.services.compliance_report_service import ObligationRapport, build_obligations_report_pdf
from backend.entrepreneur.services.compliance_score_service import compute_compliance_score
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


class FintechGapAnalysisVerrouilleError(Exception):
    """Tentative de génération avant que le questionnaire de classification

    FinTech soit entièrement répondu — traduite en 409 par le router, même
    principe que ChapitreGapAnalysisVerrouilleError côté HealthTech (voir
    project_healthtech_gap_analysis_service.py), en plus simple : un seul
    garde-fou ici, pas de chaîne de chapitres.
    """


def ensure_classification_complete(db: Session, user: User, project_id: UUID) -> None:
    """Lève FintechGapAnalysisVerrouilleError si le questionnaire n'est pas

    entièrement répondu — appelée par fintech_gap_analysis_diagnostic_
    service.run_diagnostic avant tout appel LLM (éviter un appel Groq
    coûteux pour une requête de toute façon rejetée).
    """
    project = get_owned_project(db, user, project_id)
    profile = get_or_create_fintech_profile(db, user, project.id)
    if not is_fintech_profile_complete(profile):
        raise FintechGapAnalysisVerrouilleError(
            "Réponds à toutes les questions de classification avant de générer l'analyse d'écart."
        )


def get_result(db: Session, user: User, project_id: UUID) -> ProjectFintechGapAnalysis | None:
    """Retourne `None` tant que la génération n'a jamais été déclenchée —

    contrairement à get_or_create_classification, on ne crée jamais de ligne
    vide ici : une ligne n'existe que si un vrai résultat LLM a été produit
    (même raisonnement que HealthTech : pas de ligne = pas encore généré,
    jamais une ligne à moitié remplie)."""
    project = get_owned_project(db, user, project_id)
    return db.query(ProjectFintechGapAnalysis).filter(ProjectFintechGapAnalysis.project_id == project.id).first()


def get_score(db: Session, user: User, project_id: UUID) -> ComplianceScoreRead:
    """Score de conformité FinTech : même principe que get_result, `None`

    tant que rien n'a été généré (voir compute_compliance_score, liste
    vide -> score None)."""
    row = get_result(db, user, project_id)
    accomplies: list[bool] = []
    if row is not None:
        for obligation in row.obligations.get("obligations", []):
            accomplies.append(bool(obligation.get("accompli", False)))
    return ComplianceScoreRead(
        score=compute_compliance_score(accomplies),
        total_obligations=len(accomplies),
        obligations_accomplies=sum(accomplies),
    )


def get_report_pdf(db: Session, user: User, project_id: UUID) -> bytes:
    """Meme principe que get_score : `None`/liste vide tant que rien n'a ete

    genere (voir build_obligations_report_pdf, qui gere ce cas)."""
    row = get_result(db, user, project_id)
    rapport_obligations: list[ObligationRapport] = []
    accomplies: list[bool] = []
    if row is not None:
        for obligation in row.obligations.get("obligations", []):
            accompli = bool(obligation.get("accompli", False))
            accomplies.append(accompli)
            rapport_obligations.append(
                ObligationRapport(nom=obligation["nom"], description=obligation["description"], accompli=accompli)
            )
    return build_obligations_report_pdf(
        titre="Rapport de conformite FinTech",
        obligations=rapport_obligations,
        score=compute_compliance_score(accomplies),
    )


class ObligationIndexInvalideError(Exception):
    """Même rôle que son homonyme côté HealthTech

    (project_healthtech_gap_analysis_service.py) — traduite en 404 par le
    router.
    """


def toggle_obligation(
    db: Session, user: User, project_id: UUID, obligation_index: int, accompli: bool
) -> ProjectFintechGapAnalysis:
    """Même raisonnement que project_healthtech_gap_analysis_service.

    toggle_obligation : pur suivi manuel, réassignation complète du dict
    `obligations` pour que SQLAlchemy détecte le changement JSONB."""
    project = get_owned_project(db, user, project_id)
    row = db.query(ProjectFintechGapAnalysis).filter(ProjectFintechGapAnalysis.project_id == project.id).first()
    if row is None:
        raise ObligationIndexInvalideError(
            "Aucune obligation à modifier : l'analyse d'écart n'a pas encore été générée."
        )

    obligations_liste = list(row.obligations.get("obligations", []))
    if not (0 <= obligation_index < len(obligations_liste)):
        raise ObligationIndexInvalideError(f"Index d'obligation invalide : {obligation_index}.")

    obligations_liste[obligation_index] = {**obligations_liste[obligation_index], "accompli": accompli}
    row.obligations = {"obligations": obligations_liste}
    db.commit()
    db.refresh(row)
    return row


def upsert_result(db: Session, project_id: UUID, obligations: dict, justification: str) -> ProjectFintechGapAnalysis:
    """Pas de `get_owned_project` ici : appelée côté serveur par

    fintech_gap_analysis_diagnostic_service après ses propres vérifications,
    `project_id` déjà validé en amont (même convention que
    project_healthtech_gap_analysis_service.upsert_result). Un nouveau clic
    régénère et écrase le résultat existant, pas de règle "jamais écraser un
    fait" ici (même raisonnement que HealthTech).
    """
    row = db.query(ProjectFintechGapAnalysis).filter(ProjectFintechGapAnalysis.project_id == project_id).first()
    if row is None:
        row = ProjectFintechGapAnalysis(project_id=project_id)
        db.add(row)

    row.obligations = obligations
    row.justification = justification
    db.commit()
    db.refresh(row)
    return row
