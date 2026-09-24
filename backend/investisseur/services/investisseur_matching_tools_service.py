"""Tools du matching_agent_investisseur (agents/matching_agent/investisseur_

matching_service.py) qui ont besoin d'une Session DB -- même séparation
actée que chercheur_matching_tools_service.py : `agents/` ne touche jamais
la DB directement, ces fonctions sont de simples fermetures sur (db),
injectées à l'agent au moment de l'appel.

Lecture seule, aucune écriture : la persistance du résultat reste toujours
du ressort de investisseur_matching_orchestration_service.run_matching
(upsert_result), jamais de l'agent.

2 tools (pas 4 comme côté chercheur) : un projet n'a pas d'entités
imbriquées comparables aux travaux/expertises d'un chercheur -- un résumé
déjà complet suffit la plupart du temps, lire_projet_detail ne sert qu'à
lire la description complète (non tronquée) d'un candidat précis.

Même pacing que chercheur_matching_tools_service.py (_PACING_SECONDS) :
même moteur Groq, même plafond 8000 TPM/organisation, même risque de le
dépasser en quelques secondes si les tools s'enchaînent trop vite.
"""
import time
from functools import wraps
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.shared.models.user import User

_PACING_SECONDS = 25
_MAX_CHARS_TEXTE_RETOURNE = 300


def _tronquer_texte(texte: str | None, max_chars: int = _MAX_CHARS_TEXTE_RETOURNE) -> str | None:
    if texte is None or len(texte) <= max_chars:
        return texte
    return texte[:max_chars] + " [...]"


def _avec_pacing(fn: Callable) -> Callable:
    """Même principe que _avec_pacing côté chercheur_matching_tools_

    service.py -- voir sa docstring (CORRECTIF du 23/09/2026, v4)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        time.sleep(_PACING_SECONDS)
        return result

    return wrapper


def _nom_projet(project: Project, legal_name: str | None, user: User) -> str:
    """Dénomination légale si elle existe déjà, sinon un nom de repli à

    partir du porteur de projet -- un projet en amont de l'immatriculation
    n'a souvent encore aucune identité légale (voir ProjectLegalProfile),
    l'agent a quand même besoin d'un nom à afficher dans sa recommandation."""
    if legal_name:
        return legal_name
    return f"Projet de {user.first_name} {user.last_name}".strip()


def _build_lister_projets_disponibles(db: Session, seen_project_ids: list[str]) -> Callable[[], list[dict]]:
    def lister_projets_disponibles() -> list[dict]:
        """Startups candidates en levée de fonds active, avec profil résumé."""
        rows = (
            db.query(Project, EntrepreneurProfile, User)
            .join(EntrepreneurProfile, EntrepreneurProfile.id == Project.entrepreneur_profile_id)
            .join(User, User.id == EntrepreneurProfile.user_id)
            .filter(Project.intention_levee_fonds.is_(True))
            .filter(Project.project_profile_completion == "complet")
            .all()
        )
        seen_project_ids.extend(str(project.id) for project, _, _ in rows)

        legal_names: dict[str, str | None] = {
            str(lp.project_id): lp.legal_name
            for lp in db.query(ProjectLegalProfile).filter(
                ProjectLegalProfile.project_id.in_([project.id for project, _, _ in rows])
            )
        }

        return [
            {
                "project_id": str(project.id),
                "nom": _nom_projet(project, legal_names.get(str(project.id)), user),
                "stage": project.stage,
                "sector": project.sector,
                "subsectors": project.subsectors,
                "technologies": project.technologies,
                "value_proposition": _tronquer_texte(project.value_proposition),
                "description": _tronquer_texte(project.description),
            }
            for project, _, user in rows
        ]

    return lister_projets_disponibles


def _build_lire_projet_detail(db: Session) -> Callable[[str], dict]:
    def lire_projet_detail(project_id: str) -> dict:
        """Description complète (non tronquée) d'un projet précis."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if project is None:
            return {"erreur": "projet introuvable"}
        return {
            "description": project.description,
            "value_proposition": project.value_proposition,
            "customer_segments": project.customer_segments,
            "target_users": project.target_users,
        }

    return lire_projet_detail


def build_investisseur_matching_tools(db: Session, seen_project_ids: list[str]) -> list[Callable]:
    """Construit les 2 tools du matching_agent_investisseur -- voir agents/

    matching_agent/investisseur_matching_service.py pour la définition de
    l'agent lui-même. `seen_project_ids` (liste vide fournie par l'appelant)
    est remplie par lister_projets_disponibles pendant le run --
    investisseur_matching_orchestration_service.run_matching s'en sert
    ensuite pour écarter tout project_id halluciné par l'agent."""
    return [
        _avec_pacing(_build_lister_projets_disponibles(db, seen_project_ids)),
        _avec_pacing(_build_lire_projet_detail(db)),
    ]
