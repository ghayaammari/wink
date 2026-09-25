"""Logique métier de `project_certification_obligations` — service 3.3.11

(Accompagnement accéléré vers les certifications de sécurité). V1 limitée à
SecNumCloud (voir migration q4d6f8a0b2c4).

`sync_obligations` (ajoutée le 22/09/2026 avec le 6e sous-agent de
compliance_agent) suit le même principe "jamais écraser un fait" que
project_rgpd_obligation_service.sync_obligations : une étape déjà "fait"
n'est jamais repassée à "a_faire" par une régénération. Différence
assumée avec RGPD : PAS d'archivage dans une table d'historique pour les
étapes qui disparaissent (aucune table `project_certification_obligations_
history` n'existe, voir migration q4d6f8a0b2c4) -- une étape de parcours de
certification obsolète (le référentiel a changé) n'a pas la même valeur
d'audit qu'une obligation RGPD historique, elle est simplement supprimée.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_certification_obligation import ProjectCertificationObligation
from backend.entrepreneur.schemas.compliance_score_schemas import ComplianceScoreRead
from backend.entrepreneur.schemas.project_certification_obligation_schemas import CertificationObligationCandidate
from backend.entrepreneur.services.compliance_score_service import compute_compliance_score
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User

_TYPE_CERTIFICATION = "secnumcloud"


class CertificationObligationNotFoundError(Exception):
    """Traduite en 404 par le router — obligation_id inconnu de ce projet."""


def list_obligations(db: Session, user: User, project_id: UUID) -> list[ProjectCertificationObligation]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(ProjectCertificationObligation)
        .filter(
            ProjectCertificationObligation.project_id == project.id,
            ProjectCertificationObligation.type_certification == _TYPE_CERTIFICATION,
        )
        # Ordre du parcours, pas ordre de création (voir docstring du modèle :
        # les étapes d'une certification sont séquentielles).
        .order_by(ProjectCertificationObligation.ordre)
        .all()
    )


def mark_statut(
    db: Session, user: User, project_id: UUID, obligation_id: UUID, statut: str
) -> ProjectCertificationObligation:
    project = get_owned_project(db, user, project_id)
    obligation = (
        db.query(ProjectCertificationObligation)
        .filter(
            ProjectCertificationObligation.id == obligation_id,
            ProjectCertificationObligation.project_id == project.id,
        )
        .first()
    )
    if obligation is None:
        raise CertificationObligationNotFoundError("Étape de certification introuvable.")

    obligation.statut = statut
    db.commit()
    db.refresh(obligation)
    return obligation


def get_score(db: Session, user: User, project_id: UUID) -> ComplianceScoreRead:
    """Même logique que project_rgpd_obligation_service.get_score : recalculé

    à la volée, jamais mis en cache -- pas de risque d'incohérence tant que
    le statut ne change que via mark_statut.
    """
    obligations = list_obligations(db, user, project_id)
    accomplies = [o.statut == "fait" for o in obligations]
    return ComplianceScoreRead(
        score=compute_compliance_score(accomplies),
        total_obligations=len(accomplies),
        obligations_accomplies=sum(accomplies),
    )


def sync_obligations(
    db: Session, project_id: UUID, candidates: list[CertificationObligationCandidate]
) -> list[ProjectCertificationObligation]:
    """Régénération du parcours (voir secnumcloud_diagnostic_service.py) —

    pas de `get_owned_project` ici : appelé côté serveur par la route
    d'orchestration après ses propres vérifications, `project_id` déjà validé
    en amont (même convention que project_rgpd_obligation_service.sync_obligations).
    """
    existing = {
        o.nom: o
        for o in db.query(ProjectCertificationObligation).filter(
            ProjectCertificationObligation.project_id == project_id,
            ProjectCertificationObligation.type_certification == _TYPE_CERTIFICATION,
        )
    }
    candidate_noms = {c.nom for c in candidates}

    # 1. Étapes qui disparaissent (plus proposées par l'agent) : supprimées
    # sans archivage -- voir docstring module pour pourquoi (contrairement à
    # RGPD, pas de table d'historique pour ce service).
    for nom, obligation in existing.items():
        if nom not in candidate_noms:
            db.delete(obligation)

    # 2. Étapes proposées : upsert par nom, sans jamais repasser fait -> a_faire.
    for candidate in candidates:
        obligation = existing.get(candidate.nom)
        if obligation is None:
            db.add(
                ProjectCertificationObligation(
                    project_id=project_id,
                    type_certification=_TYPE_CERTIFICATION,
                    nom=candidate.nom,
                    description=candidate.description,
                    ordre=candidate.ordre,
                    legal_text_id=candidate.legal_text_id,
                )
            )
        else:
            obligation.description = candidate.description
            obligation.ordre = candidate.ordre
            obligation.legal_text_id = candidate.legal_text_id
            # statut volontairement non touché : "jamais écraser un fait".

    db.commit()
    return list(
        db.query(ProjectCertificationObligation)
        .filter(
            ProjectCertificationObligation.project_id == project_id,
            ProjectCertificationObligation.type_certification == _TYPE_CERTIFICATION,
        )
        .order_by(ProjectCertificationObligation.ordre)
        .all()
    )
