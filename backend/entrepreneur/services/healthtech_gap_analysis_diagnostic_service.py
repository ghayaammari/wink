"""Orchestration du diagnostic d'ecart HealthTech -- service 3.3.6, un chapitre

a la fois. Version agentique (pilote) : ce fichier ne fait plus le RAG lui-
meme (embedding + recherche vectorielle) avant d'appeler l'agent -- il
construit seulement les tools (voir compliance_agent_tools_service.py,
fermes sur la Session courante) et laisse l'agent decider quoi consulter.
Reste le seul endroit qui relie le statut du chapitre (verrouillage) et
l'agent conformite (agents/compliance_agent/healthtech_gap_analysis_service.py),
avant de persister via project_healthtech_gap_analysis_service.upsert_result.

Différence avec RGPD/AI Act (pas encore convertis a ce pattern) : ceux-la
continuent de pre-calculer eux-memes leur requete d'embedding et d'appeler
search_similar_chunks directement, en attendant leur propre conversion
(service par service, voir conversation produit).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.compliance_agent.healthtech_gap_analysis_service import (
    ObligationGap,
    generate_gap_analysis,
)
from backend.entrepreneur.models.project_healthtech_gap_analysis import ProjectHealthtechGapAnalysis
from backend.entrepreneur.schemas.project_healthtech_gap_analysis_schemas import ChapitreHealthtech
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.healthtech_gap_analysis_chapitres import CHAPITRES_GAP_ANALYSIS_HEALTHTECH
from backend.entrepreneur.services.project_healthtech_gap_analysis_service import (
    ChapitreGapAnalysisInconnuError,
    ensure_chapitre_debloque,
    upsert_result,
)
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User


def _get_chapitre_titre(chapitre_cle: ChapitreHealthtech) -> str:
    for chapitre in CHAPITRES_GAP_ANALYSIS_HEALTHTECH:
        if chapitre.cle == chapitre_cle:
            return chapitre.titre
    raise ChapitreGapAnalysisInconnuError(f"Chapitre inconnu : '{chapitre_cle}'.")


def _get_requete_semantique(chapitre_cle: ChapitreHealthtech) -> str:
    for chapitre in CHAPITRES_GAP_ANALYSIS_HEALTHTECH:
        if chapitre.cle == chapitre_cle:
            return chapitre.requete_semantique
    raise ChapitreGapAnalysisInconnuError(f"Chapitre inconnu : '{chapitre_cle}'.")


def _obligations_to_dict(obligations: list[ObligationGap], seen_source_ids: list[str]) -> list[dict]:
    """Valide chaque source_id renvoye par l'agent contre les chunks

    reellement vus via l'outil rechercher_corpus_reglementaire pendant ce
    run -- l'agent choisit lui-meme quoi chercher (et combien de fois), donc
    contrairement a l'ancienne verification par index de liste (bornes
    fixes), on verifie ici l'appartenance a l'ensemble reellement vu pendant
    la tache. Un source_id absent de cet ensemble (LLM qui hallucine) donne
    source_id: None, pas une erreur -- l'obligation est quand meme
    conservee, coherent avec le comportement precedent.
    """
    seen = set(seen_source_ids)
    result = []
    for obligation in obligations:
        source_id = obligation.source_id if obligation.source_id in seen else None
        result.append(
            {"nom": obligation.nom, "description": obligation.description, "source_id": source_id, "accompli": False}
        )
    return result


def run_chapter_diagnostic(
    db: Session, user: User, project_id: UUID, chapitre_cle: ChapitreHealthtech
) -> ProjectHealthtechGapAnalysis:
    """Point d'entree du service 3.3.6 (volet HealthTech) : declenche

    uniquement par un clic explicite sur le chapitre cote frontend (jamais
    automatique, voir docstring du modele) -- chaque appel coute un ou
    plusieurs appels LLM reels (l'agent peut chercher plusieurs fois),
    contrairement au recalcul gratuit de la classification.
    """
    project = get_owned_project(db, user, project_id)
    ensure_chapitre_debloque(db, user, project.id, chapitre_cle)

    chapitre_titre = _get_chapitre_titre(chapitre_cle)
    requete_semantique = _get_requete_semantique(chapitre_cle)

    seen_source_ids: list[str] = []
    tools = build_compliance_agent_tools(db, user, project.id, seen_source_ids)

    result = generate_gap_analysis(chapitre_titre, requete_semantique, tools)
    obligations = _obligations_to_dict(result.obligations, seen_source_ids)

    return upsert_result(db, project.id, chapitre_cle, {"obligations": obligations}, result.justification)
