"""Logique métier de `project_healthtech_gap_analysis` — service 3.3.6,

volet HealthTech (mini-roadmap à 3 chapitres). Contient le calcul du statut
de chaque chapitre (verrouillé/débloqué/fait — dérivé de la présence des
lignes existantes, jamais stocké, voir docstring du modèle) et la persistance
du résultat d'un chapitre généré.

Même séparation que RGPD/AI Act/détection sectorielle : ce fichier ne fait
aucun appel LLM ni recherche vectorielle (voir healthtech_gap_analysis_
diagnostic_service.py pour l'orchestration RAG + agent), il ne connaît que
project_healthtech_gap_analysis et le registre de chapitres.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_healthtech_gap_analysis import ProjectHealthtechGapAnalysis
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.project_healthtech_gap_analysis_schemas import (
    ChapitreGapAnalysisStatusRead,
    ChapitreHealthtech,
)
from backend.entrepreneur.services.healthtech_data_profile_service import (
    get_or_create_profile as get_or_create_healthtech_profile,
    is_profile_complete as is_healthtech_profile_complete,
)
from backend.entrepreneur.services.compliance_report_service import ObligationRapport, build_obligations_report_pdf
from backend.entrepreneur.services.compliance_score_service import compute_compliance_score
from backend.entrepreneur.services.healthtech_gap_analysis_chapitres import CHAPITRES_GAP_ANALYSIS_HEALTHTECH
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


class ChapitreGapAnalysisInconnuError(Exception):
    """`chapitre` ne correspond à aucune clé de CHAPITRES_GAP_ANALYSIS_HEALTHTECH — traduite en 404 par le router."""


class ChapitreGapAnalysisVerrouilleError(Exception):
    """Tentative de génération sur un chapitre encore verrouillé (le précédent

    n'a pas de résultat) — traduite en 409 par le router, jamais en 400 :
    la requête est valide, c'est l'état actuel du projet qui l'interdit.
    """


def _get_existing_rows(db: Session, project_id: UUID) -> dict[str, ProjectHealthtechGapAnalysis]:
    rows = (
        db.query(ProjectHealthtechGapAnalysis)
        .filter(ProjectHealthtechGapAnalysis.project_id == project_id)
        .all()
    )
    return {row.chapitre: row for row in rows}


def get_chapter_status_list(db: Session, user: User, project_id: UUID) -> list[ChapitreGapAnalysisStatusRead]:
    """Un élément par chapitre, dans l'ordre de CHAPITRES_GAP_ANALYSIS_HEALTHTECH

    (ordre significatif : reflète le cycle de vie réglementaire MDR, voir
    docstring du registre). Le premier chapitre n'est "debloque" que si le
    questionnaire de classification (étape précédente du parcours, voir
    frontend SectorDiagnosticPage) est entièrement répondu — sinon
    "verrouille" comme n'importe quel chapitre suivant non débloqué. Un
    chapitre suivant n'est "debloque" que si le précédent a un résultat —
    jamais l'inverse (pas de saut de chapitre).
    """
    project = get_owned_project(db, user, project_id)
    existing = _get_existing_rows(db, project.id)
    profile = get_or_create_healthtech_profile(db, user, project.id)

    statuses: list[ChapitreGapAnalysisStatusRead] = []
    chapitre_precedent_fait = is_healthtech_profile_complete(profile)
    for chapitre in CHAPITRES_GAP_ANALYSIS_HEALTHTECH:
        row = existing.get(chapitre.cle)
        if row is not None:
            statut = "fait"
        elif chapitre_precedent_fait:
            statut = "debloque"
        else:
            statut = "verrouille"

        statuses.append(
            ChapitreGapAnalysisStatusRead(
                cle=chapitre.cle,
                titre=chapitre.titre,
                statut=statut,
                resultat=row,
            )
        )
        chapitre_precedent_fait = row is not None

    return statuses


def get_score(db: Session, user: User, project_id: UUID) -> ComplianceScoreRead:
    """Score de conformité HealthTech : un seul score agrégeant les

    obligations de tous les chapitres déjà générés (pas un score par
    chapitre — le diagnostic HealthTech est un tout, découpé en chapitres
    uniquement pour l'UX de génération progressive, voir docstring de
    get_chapter_status_list). Un chapitre pas encore généré ne contribue
    aucune obligation, ni au numérateur ni au dénominateur.
    """
    project = get_owned_project(db, user, project_id)
    rows = _get_existing_rows(db, project.id)
    accomplies: list[bool] = []
    for row in rows.values():
        for obligation in row.obligations.get("obligations", []):
            accomplies.append(bool(obligation.get("accompli", False)))
    return ComplianceScoreRead(
        score=compute_compliance_score(accomplies),
        total_obligations=len(accomplies),
        obligations_accomplies=sum(accomplies),
    )


def get_report_pdf(db: Session, user: User, project_id: UUID) -> bytes:
    """Rapport telechargeable agregeant tous les chapitres deja generes --

    meme perimetre que get_score (un seul rapport pour tout le diagnostic
    HealthTech, pas un par chapitre)."""
    project = get_owned_project(db, user, project_id)
    rows = _get_existing_rows(db, project.id)
    rapport_obligations: list[ObligationRapport] = []
    accomplies: list[bool] = []
    for row in rows.values():
        for obligation in row.obligations.get("obligations", []):
            accompli = bool(obligation.get("accompli", False))
            accomplies.append(accompli)
            rapport_obligations.append(
                ObligationRapport(nom=obligation["nom"], description=obligation["description"], accompli=accompli)
            )
    return build_obligations_report_pdf(
        titre="Rapport de conformite HealthTech",
        obligations=rapport_obligations,
        score=compute_compliance_score(accomplies),
    )


def ensure_chapitre_debloque(db: Session, user: User, project_id: UUID, chapitre_cle: ChapitreHealthtech) -> None:
    """Lève ChapitreGapAnalysisVerrouilleError si `chapitre_cle` n'est pas

    "debloque" ou "fait" — appelée par healthtech_gap_analysis_diagnostic_
    service.run_chapter_diagnostic avant tout appel LLM (éviter un appel
    Groq coûteux pour une requête qui sera de toute façon rejetée).
    """
    statuses = get_chapter_status_list(db, user, project_id)
    for status_item in statuses:
        if status_item.cle == chapitre_cle:
            if status_item.statut == "verrouille":
                raise ChapitreGapAnalysisVerrouilleError(
                    f"Le chapitre '{chapitre_cle}' est verrouillé : termine d'abord la classification "
                    "(ou le chapitre précédent) avant de le générer."
                )
            return
    raise ChapitreGapAnalysisInconnuError(f"Chapitre inconnu : '{chapitre_cle}'.")


class ObligationIndexInvalideError(Exception):
    """`obligation_index` hors limites (ou chapitre pas encore généré) —

    traduite en 404 par le router.
    """


def toggle_obligation(
    db: Session,
    user: User,
    project_id: UUID,
    chapitre_cle: ChapitreHealthtech,
    obligation_index: int,
    accompli: bool,
) -> ProjectHealthtechGapAnalysis:
    """Marque une obligation comme accomplie ou non — pur suivi manuel côté

    entrepreneur, aucun recalcul ni appel LLM ici (contrairement à
    upsert_result, jamais appelée par cette fonction). Réassigne le dict
    complet `obligations` (jamais une mutation en place de la liste
    imbriquée) : SQLAlchemy ne détecte pas une mutation interne à un
    dict/list Python existant sur une colonne JSONB sans MutableDict,
    inutile d'introduire cette dépendance pour ce seul besoin.
    """
    project = get_owned_project(db, user, project_id)
    row = (
        db.query(ProjectHealthtechGapAnalysis)
        .filter(
            ProjectHealthtechGapAnalysis.project_id == project.id,
            ProjectHealthtechGapAnalysis.chapitre == chapitre_cle,
        )
        .first()
    )
    if row is None:
        raise ObligationIndexInvalideError(
            f"Aucune obligation à modifier : le chapitre '{chapitre_cle}' n'a pas encore été généré."
        )

    obligations_liste = list(row.obligations.get("obligations", []))
    if not (0 <= obligation_index < len(obligations_liste)):
        raise ObligationIndexInvalideError(f"Index d'obligation invalide : {obligation_index}.")

    obligations_liste[obligation_index] = {**obligations_liste[obligation_index], "accompli": accompli}
    row.obligations = {"obligations": obligations_liste}
    db.commit()
    db.refresh(row)
    return row


def upsert_result(
    db: Session, project_id: UUID, chapitre_cle: ChapitreHealthtech, obligations: dict, justification: str
) -> ProjectHealthtechGapAnalysis:
    """Crée ou remplace le résultat d'un chapitre. Pas de `get_owned_project`

    ici : appelée côté serveur par healthtech_gap_analysis_diagnostic_service
    après ses propres vérifications, `project_id` déjà validé en amont (même
    convention que project_rgpd_obligation_service.sync_obligations). Un
    nouveau clic sur un chapitre déjà "fait" régénère et écrase son résultat
    — pas de règle "jamais écraser un fait" ici (contrairement au statut
    RGPD `a_faire`/`fait`) : il n'y a pas de statut manuel à préserver, la
    génération est le seul contenu de la ligne.
    """
    row = (
        db.query(ProjectHealthtechGapAnalysis)
        .filter(
            ProjectHealthtechGapAnalysis.project_id == project_id,
            ProjectHealthtechGapAnalysis.chapitre == chapitre_cle,
        )
        .first()
    )
    if row is None:
        row = ProjectHealthtechGapAnalysis(project_id=project_id, chapitre=chapitre_cle)
        db.add(row)

    row.obligations = obligations
    row.justification = justification
    db.commit()
    db.refresh(row)
    return row
