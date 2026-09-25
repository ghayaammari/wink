"""Logique métier de `project_certification_estimations` — service 3.3.11.

Fichier séparé de project_certification_obligation_service.py (une table,
une responsabilité chacune — voir modèle project_certification_estimation.py :
c'est une estimation globale du parcours, pas une propriété d'une étape).

`save_estimation` est le point d'entrée que secnumcloud_diagnostic_service.py
utilise pour écrire le résultat de l'agent : remplace toujours la ligne
existante (UniqueConstraint project_id + type_certification), jamais
d'historique ici (voir docstring du modèle — une ré-estimation n'a pas besoin
d'être tracée dans le temps, contrairement aux obligations RGPD).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.project_certification_estimation import ProjectCertificationEstimation

_TYPE_CERTIFICATION = "secnumcloud"


def get_estimation(db: Session, project_id: UUID) -> ProjectCertificationEstimation | None:
    """Lecture seule : None tant qu'aucun parcours n'a été généré pour ce

    projet (même convention que score=None avant premier diagnostic sur les
    autres domaines)."""
    return (
        db.query(ProjectCertificationEstimation)
        .filter(
            ProjectCertificationEstimation.project_id == project_id,
            ProjectCertificationEstimation.type_certification == _TYPE_CERTIFICATION,
        )
        .first()
    )


def save_estimation(
    db: Session,
    project_id: UUID,
    *,
    delai_mois_min: int,
    delai_mois_max: int,
    cout_estime_min: int,
    cout_estime_max: int,
    justification: str,
) -> ProjectCertificationEstimation:
    """Remplace l'estimation existante (ou en crée une) — pas de

    `get_owned_project` ici : appelé côté serveur par la route d'orchestration
    après ses propres vérifications, même convention que
    project_rgpd_obligation_service.sync_obligations.
    """
    existing = get_estimation(db, project_id)
    if existing is not None:
        existing.delai_mois_min = delai_mois_min
        existing.delai_mois_max = delai_mois_max
        existing.cout_estime_min = cout_estime_min
        existing.cout_estime_max = cout_estime_max
        existing.justification = justification
        db.commit()
        db.refresh(existing)
        return existing

    estimation = ProjectCertificationEstimation(
        project_id=project_id,
        type_certification=_TYPE_CERTIFICATION,
        delai_mois_min=delai_mois_min,
        delai_mois_max=delai_mois_max,
        cout_estime_min=cout_estime_min,
        cout_estime_max=cout_estime_max,
        justification=justification,
    )
    db.add(estimation)
    db.commit()
    db.refresh(estimation)
    return estimation
