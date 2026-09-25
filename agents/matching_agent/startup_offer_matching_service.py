"""Agent de matching Startup-Offres (EPIC-06) — trouve, parmi les offres

d'investissement ouvertes sur Wink, celles pertinentes pour LE PROJET d'un
entrepreneur, classées par ordre de pertinence avec une explication de
chaque rang. Sens inverse de investisseur_matching_service.py (Investisseur
-> Startup) -- ici Startup -> Offres.

Même moteur que investisseur_matching_service.py (agents/shared/groq_
runtime/react_agent_runner.py, run_react_agent) : un ChatGroq + system
prompt (agents/config/prompts.yaml, matching_agent_startup.system) + les
tools (construits côté backend/entrepreneur/services/startup_offer_
matching_tools_service.py, fermés sur db -- agents/ ne touche jamais la DB
directement) + response_format qui force la sortie dans OfferMatchingResult.

Même optimisation que investisseur_matching_service.py (CORRECTIF v3) : le
projet est embarqué directement dans le message de tâche, pas de tool
lire_projet -- un aller-retour LLM de moins.
"""
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 15


class StartupOfferMatchingAgentError(ReactAgentError):
    """Échec d'appel à l'agent (LLM/Groq) ou réponse hors schéma."""


class OfferMatch(BaseModel):
    offer_id: str = Field(description="Id vu via lister_offres_disponibles, jamais inventé.")
    rang: int = Field(ge=1, description="1 = le plus pertinent, sans trou, jamais de doublon.")
    niveau_pertinence: Literal["fort", "moyen", "faible"]
    explication: str = Field(description="Concrète, citant l'info exacte utilisée -- jamais vague.")


class OfferMatchingResult(BaseModel):
    matches: list[OfferMatch] = Field(description="Seulement les offres pertinentes, liste vide si aucune.")
    synthese: str = Field(description="1-2 phrases sur la démarche suivie.")


def match_offers(tools: list[Callable], projet: dict) -> OfferMatchingResult:
    """Appelée uniquement par startup_offer_matching_orchestration_service.

    run_matching(), sur déclenchement explicite (bouton "Visualiser les
    offres" côté frontend) -- jamais automatique, même raisonnement que
    match_startups.

    `projet` : dict {stage, secteur, sous-secteurs, technologies,
    value_proposition, description} -- construit par startup_offer_
    matching_orchestration_service.run_matching, injecté tel quel dans le
    message de tâche."""
    config = get_llm_config()["matching_agent_startup"]["matching"]
    system_prompt = get_prompts()["matching_agent_startup"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=OfferMatchingResult,
            task_message=(
                f"Projet : {projet}\n\n"
                "Trouve les offres d'investissement pertinentes, classe-les par ordre de pertinence "
                "et explique ton classement."
            ),
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise StartupOfferMatchingAgentError(str(exc)) from exc
