"""Logique métier de `project_rgpd_obligations` (+ archivage dans
`project_rgpd_obligations_history`) — service 3.3.1 (RGPD).

`sync_obligations` est le point d'entrée que le compliance_agent (via
la route d'orchestration qui l'appelle) utilisera pour écrire ses obligations
candidates — l'agent ne fait jamais lui-même d'accès DB (voir séparation
agents/ vs backend/<acteur>/services/), il retourne une liste de
`RgpdObligationCandidate` à ce service, qui applique les règles métier.

Règle "jamais écraser un fait" (même principe que roadmap_service pour
`startup_roadmap_items.statut`) : une obligation déjà `fait` n'est jamais
repassée à `a_faire` par une régénération, qu'elle soit ou non reproposée par
l'agent. Correspondance par `nom` (dette technique assumée, voir modèle
project_rgpd_obligation.py).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_rgpd_obligation import ProjectRgpdObligation
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.models.project_rgpd_obligation_history import ProjectRgpdObligationHistory
from backend.entrepreneur.schemas.project_rgpd_obligation_schemas import RgpdObligationCandidate
from backend.entrepreneur.services.compliance_report_service import ObligationRapport, build_obligations_report_pdf
from backend.entrepreneur.services.compliance_score_service import compute_compliance_score
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


class RgpdObligationNotFoundError(Exception):
    """Traduite en 404 par le router — obligation_id inconnu de ce projet."""


def list_obligations(db: Session, user: User, project_id: UUID) -> list[ProjectRgpdObligation]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(ProjectRgpdObligation)
        .filter(ProjectRgpdObligation.project_id == project.id)
        .order_by(ProjectRgpdObligation.created_at)
        .all()
    )


def mark_statut(
    db: Session, user: User, project_id: UUID, obligation_id: UUID, statut: str
) -> ProjectRgpdObligation:
    project = get_owned_project(db, user, project_id)
    obligation = (
        db.query(ProjectRgpdObligation)
        .filter(ProjectRgpdObligation.id == obligation_id, ProjectRgpdObligation.project_id == project.id)
        .first()
    )
    if obligation is None:
        raise RgpdObligationNotFoundError("Obligation introuvable.")

    obligation.statut = statut
    db.commit()
    db.refresh(obligation)
    return obligation


def get_score(db: Session, user: User, project_id: UUID) -> ComplianceScoreRead:
    """Score de conformité RGPD : pourcentage d'obligations au statut "fait"

    parmi celles listées pour ce projet. Recalculé à la volée à chaque appel
    (pas stocké) : aucune obligation ne pouvant changer de statut sans passer
    par mark_statut/sync_obligations, il n'y a aucun risque d'incohérence à
    recalculer plutôt qu'à mettre en cache.
    """
    obligations = list_obligations(db, user, project_id)
    accomplies = [o.statut == "fait" for o in obligations]
    return ComplianceScoreRead(
        score=compute_compliance_score(accomplies),
        total_obligations=len(accomplies),
        obligations_accomplies=sum(accomplies),
    )


def get_report_pdf(db: Session, user: User, project_id: UUID) -> bytes:
    """Rapport telechargeable (voir compliance_report_service.py) -- appele

    uniquement au clic sur "Terminer" cote copilot (frontend), jamais depuis
    la page de diagnostic normale (voir docstring RgpdDiagnosticPage.tsx).
    """
    obligations = list_obligations(db, user, project_id)
    score = compute_compliance_score([o.statut == "fait" for o in obligations])
    rapport_obligations = [
        ObligationRapport(nom=o.nom, description=o.description, accompli=o.statut == "fait") for o in obligations
    ]
    return build_obligations_report_pdf(
        titre="Rapport de conformite RGPD", obligations=rapport_obligations, score=score
    )


def sync_obligations(db: Session, project_id: UUID, candidates: list[RgpdObligationCandidate]) -> list[ProjectRgpdObligation]:
    """Régénération majeure : appelée après un changement significatif du

    profil (compliance_data_profile), pas à chaque petite modification (voir
    décision actée, docstring de project_rgpd_obligations_history). Pas de
    `get_owned_project` ici : appelé côté serveur par la route d'orchestration
    après ses propres vérifications, `project_id` déjà validé en amont.
    """
    existing = {
        o.nom: o for o in db.query(ProjectRgpdObligation).filter(ProjectRgpdObligation.project_id == project_id)
    }
    candidate_noms = {c.nom for c in candidates}

    # 1. Obligations qui disparaissent (plus proposées par l'agent) : archivées
    # puis supprimées, quel que soit leur statut. "Jamais écraser un fait" porte
    # sur le sens fait -> a_faire, pas sur l'interdiction d'archiver une ligne
    # devenue obsolète.
    for nom, obligation in existing.items():
        if nom not in candidate_noms:
            db.add(
                ProjectRgpdObligationHistory(
                    project_id=project_id,
                    nom=obligation.nom,
                    description=obligation.description,
                    statut=obligation.statut,
                    lie_a_aipd=obligation.lie_a_aipd,
                )
            )
            db.delete(obligation)

    # 2. Obligations proposées : upsert par nom, sans jamais repasser fait -> a_faire.
    for candidate in candidates:
        obligation = existing.get(candidate.nom)
        if obligation is None:
            db.add(
                ProjectRgpdObligation(
                    project_id=project_id,
                    nom=candidate.nom,
                    description=candidate.description,
                    legal_text_id=candidate.legal_text_id,
                    lie_a_aipd=candidate.lie_a_aipd,
                )
            )
        else:
            obligation.description = candidate.description
            obligation.legal_text_id = candidate.legal_text_id
            obligation.lie_a_aipd = candidate.lie_a_aipd
            # statut volontairement non touché : "jamais écraser un fait".

    db.commit()
    return list(db.query(ProjectRgpdObligation).filter(ProjectRgpdObligation.project_id == project_id).all())