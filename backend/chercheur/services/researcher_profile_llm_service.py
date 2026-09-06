"""Service — appels LLM (Qwen via Groq) pour les résumés de profil chercheur.

Même séparation que paper_llm_service.py : ne touche jamais la base de
données, retourne du texte brut. L'orchestration (session DB, écriture via
researcher_field_value_service) reste dans researcher_summary_service.py.

Deux résumés distincts, chacun régénérable indépendamment (voir
researcher_field_value_service.SINGLE_VALUE_FIELDS, qui contient déjà
expertise_summary et research_work_summary) :
1. generate_expertise_summary — à partir de researcher_past_expertises.
2. generate_research_work_summary — à partir des research_works du profil.

Contrairement à paper_llm_service, la sortie voulue ici est un texte unique,
pas plusieurs champs structurés — mais response_format=json_object (voir
llm_client.call_and_parse) exige quand même un objet JSON côté API Groq, donc
on demande une seule clé "summary" plutôt que de désactiver ce mode pour ce
cas isolé (le mode json_object réduit aussi les échecs de parsing sur du
texte libre long, même avec une seule clé)."""
import logging

from backend.chercheur.services.llm_client import call_and_parse

logger = logging.getLogger(__name__)


def generate_expertise_summary(expertises: list[dict]) -> str:
    """expertises : liste de dicts avec organization_name, domain,
    mission_type, period_label, description (voir PastExpertiseRead).
    Retourne une chaîne vide si la liste est vide — à l'appelant de ne pas
    déclencher la génération dans ce cas plutôt que de gaspiller un appel
    LLM pour rien (voir researcher_summary_service)."""
    if not expertises:
        return ""

    formatted = "\n".join(
        f"- {e.get('organization_name')} "
        f"({e.get('period_label') or 'période non précisée'}) : "
        f"{e.get('mission_type') or 'mission non précisée'} en {e.get('domain') or 'domaine non précisé'}. "
        f"{e.get('description') or ''}".strip()
        for e in expertises
    )

    prompt = f"""Voici la liste des expériences professionnelles passées d'un chercheur :

{formatted}

Rédige un résumé synthétique en 4-6 phrases de son expertise professionnelle globale, à partir de ces expériences. Ce résumé sera affiché sur son profil pour permettre à des startups de comprendre rapidement son parcours et ses compétences pratiques (pas seulement académiques).

Réponds UNIQUEMENT en JSON valide avec une seule clé "summary". Aucun texte autour, aucun bloc de code."""

    result = call_and_parse(prompt, max_tokens=600)
    logger.info("Résultat brut LLM (expertise_summary) : %r", result)
    return result.get("summary", "")


def generate_research_work_summary(works: list[dict]) -> str:
    """works : liste de dicts avec au moins title et abstract (voir
    ResearchWork). Retourne une chaîne vide si la liste est vide.

    Volontairement basé sur title + abstract, jamais sur paper_summary
    (champ généré par travail, peut être absent si son analyse LLM
    individuelle a échoué — voir research_extraction_service) : un résumé de
    profil moins riche mais qui fonctionne pour 100% des travaux vaut mieux
    qu'un résumé plus fin mais qui ignore silencieusement certains travaux."""
    if not works:
        return ""

    formatted = "\n".join(
        f"- {w.get('title')}" + (f" : {w.get('abstract')}" if w.get("abstract") else "") for w in works
    )

    prompt = f"""Voici la liste des travaux de recherche publiés par un chercheur :

{formatted}

Rédige un résumé synthétique en 4-6 phrases de l'ensemble de ses travaux de recherche — les thématiques récurrentes, les axes de recherche principaux, la portée globale de son travail. Ce résumé sera utilisé pour mettre en correspondance ce chercheur avec des startups ayant un besoin scientifique déclaré (matching futur, I6) — il doit donner une image complète et exploitable de son domaine d'expertise scientifique.

Réponds UNIQUEMENT en JSON valide avec une seule clé "summary". Aucun texte autour, aucun bloc de code."""

    result = call_and_parse(prompt, max_tokens=800)
    logger.info("Résultat brut LLM (research_work_summary) : %r", result)
    return result.get("summary", "")