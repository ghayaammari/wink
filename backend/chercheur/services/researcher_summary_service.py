"""Orchestration des résumés de profil générés par LLM — expertise_summary
(à partir de researcher_past_expertises) et research_work_summary (à partir
de research_works). Même séparation que research_extraction_service.py vis-
à-vis de paper_llm_service.py : ce fichier gère la session DB et l'écriture,
researcher_profile_llm_service.py ne fait que l'appel LLM.

Chaque résumé est généré et validé indépendamment (deux boutons séparés côté
frontend, deux fonctions séparées ici) — un échec sur l'un n'affecte jamais
l'autre, même logique que _generate_and_store_analysis par travail.

Tâches de fond (BackgroundTasks) : chaque fonction ouvre sa propre session
DB (SessionLocal), jamais celle de la requête d'origine — déjà fermée quand
la tâche s'exécute (même remarque que research_extraction_service.py)."""
import logging
import uuid

from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.models.researcher_past_expertise import ResearcherPastExpertise
from backend.chercheur.services import researcher_field_value_service, researcher_profile_llm_service
from backend.chercheur.services.llm_client import LLMExtractionError
from backend.shared.database import SessionLocal

logger = logging.getLogger(__name__)

# Si paper_summary n'a pas encore été confirmé pour ce travail (ex: analyse
# LLM individuelle jamais faite ou pas encore validée), on retombe sur
# l'abstract tronqué plutôt que d'ignorer purement le travail — voir
# discussion du 05/09/2026 : mieux vaut un texte moins riche pour ce travail
# que de le faire disparaître silencieusement du résumé global.
FALLBACK_ABSTRACT_CHARS = 300


def generate_expertise_summary(researcher_profile_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        expertises = (
            db.query(ResearcherPastExpertise).filter_by(researcher_profile_id=researcher_profile_id).all()
        )
        if not expertises:
            # Rien à résumer — pas une erreur, juste un chercheur qui n'a pas
            # encore renseigné d'expertise passée (service optionnel, jamais
            # demandé à l'onboarding).
            logger.info(
                "Aucune expertise passée pour researcher_profile_id=%s — rien à résumer.", researcher_profile_id
            )
            return

        expertise_dicts = [
            {
                "organization_name": e.organization_name,
                "domain": e.domain,
                "mission_type": e.mission_type,
                "period_label": e.period_label,
                "description": e.description,
            }
            for e in expertises
        ]

        try:
            summary = researcher_profile_llm_service.generate_expertise_summary(expertise_dicts)
        except LLMExtractionError as exc:
            logger.warning(
                "Génération du résumé d'expertise échouée pour researcher_profile_id=%s : %s",
                researcher_profile_id,
                exc,
            )
            return

        if not summary:
            return

        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=researcher_profile_id,
            field_name="expertise_summary",
            field_value=summary,
            source="llm_generated",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _get_confirmed_paper_summary(db, work_id: uuid.UUID) -> str | None:
    """paper_summary n'est jamais une colonne sur ResearchWork (voir
    research_work.py : seules les métadonnées bibliographiques brutes sont
    des colonnes directes) — uniquement une ligne researcher_field_values,
    entity_type='research_work'. On ne lit que la version confirmée : une
    version encore pending_confirmation n'a pas été validée par le chercheur,
    donc pas fiable pour un résumé affiché ailleurs."""
    row = (
        db.query(ResearcherFieldValue)
        .filter_by(
            entity_type="research_work",
            entity_id=work_id,
            field_name="paper_summary",
            validation_status="confirmed",
        )
        .first()
    )
    return row.field_value if row else None


def generate_research_work_summary(researcher_profile_id: uuid.UUID) -> None:
    """Utilise paper_summary confirmé de chaque travail (résumé condensé,
    généré individuellement par paper_llm_service puis validé par le
    chercheur — voir _get_confirmed_paper_summary), jamais title+abstract
    complet. Réduit fortement la taille du prompt envoyé au LLM par rapport
    à l'ancienne approche (abstract intégral de chaque travail), qui avait
    causé un 413 Payload Too Large côté Groq avec plusieurs travaux (voir
    échange du 05/09/2026).

    Si paper_summary est absent/non confirmé pour un travail, on retombe sur
    l'abstract tronqué plutôt que d'ignorer ce travail — cohérent avec le
    choix d'origine de ne perdre aucun travail silencieusement."""
    db = SessionLocal()
    try:
        works = db.query(ResearchWork).filter_by(researcher_profile_id=researcher_profile_id).all()
        if not works:
            logger.info(
                "Aucun travail de recherche pour researcher_profile_id=%s — rien à résumer.", researcher_profile_id
            )
            return

        work_dicts = [
            {
                "title": w.title,
                "summary_text": _get_confirmed_paper_summary(db, w.id) or (w.abstract or "")[:FALLBACK_ABSTRACT_CHARS],
            }
            for w in works
        ]

        try:
            summary = researcher_profile_llm_service.generate_research_work_summary(work_dicts)
        except LLMExtractionError as exc:
            logger.warning(
                "Génération du résumé de travaux échouée pour researcher_profile_id=%s : %s",
                researcher_profile_id,
                exc,
            )
            return

        if not summary:
            return

        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=researcher_profile_id,
            field_name="research_work_summary",
            field_value=summary,
            source="llm_generated",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()