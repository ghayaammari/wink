"""Agent de matching Investisseur-Startup (EPIC-07) — trouve, parmi les

startups inscrites sur Wink en levée de fonds active, celles pertinentes
pour une offre d'investissement déclarée par un investisseur
(investment_offers), classées par ordre de pertinence avec une explication
de chaque rang. Sens inverse de chercheur_matching_service.py (Recherche ->
Startup) -- ici Investisseur -> Startup.

Même moteur que chercheur_matching_service.py (agents/shared/groq_runtime/
react_agent_runner.py, run_react_agent) : un ChatGroq + system prompt
(agents/config/prompts.yaml, matching_agent_investisseur.system) + les
tools (construits côté backend/investisseur/services/investisseur_
matching_tools_service.py, fermés sur db -- agents/ ne touche jamais la DB
directement) + response_format qui force la sortie dans
StartupMatchingResult.

Même optimisation que chercheur_matching_service.py (CORRECTIF v3) :
l'offre est embarquée directement dans le message de tâche, pas de tool
lire_offre -- un aller-retour LLM de moins.
"""
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 15


class InvestisseurMatchingAgentError(ReactAgentError):
    """Échec d'appel à l'agent (LLM/Groq) ou réponse hors schéma."""


class StartupMatch(BaseModel):
    project_id: str = Field(description="Id vu via lister_projets_disponibles, jamais inventé.")
    nom: str
    rang: int = Field(ge=1, description="1 = le plus pertinent, sans trou, jamais de doublon.")
    niveau_pertinence: Literal["fort", "moyen", "faible"]
    explication: str = Field(description="Concrète, citant l'info exacte utilisée -- jamais vague.")


class StartupMatchingResult(BaseModel):
    matches: list[StartupMatch] = Field(description="Seulement les startups pertinentes, liste vide si aucune.")
    synthese: str = Field(description="1-2 phrases sur la démarche suivie.")


def match_startups(tools: list[Callable], offre: dict) -> StartupMatchingResult:
    """Appelée uniquement par investisseur_matching_orchestration_service.

    run_matching(), sur déclenchement explicite (bouton "Visualiser" côté
    frontend) -- jamais automatique au dépôt de l'offre, même raisonnement
    que match_chercheurs.

    `offre` : dict {titre, description, montant_propose, secteurs_cibles,
    stades_cibles, investisseur: {...}} -- construit par investisseur_
    matching_orchestration_service.run_matching, injecté tel quel dans le
    message de tâche."""
    config = get_llm_config()["matching_agent_investisseur"]["matching"]
    system_prompt = get_prompts()["matching_agent_investisseur"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=StartupMatchingResult,
            task_message=(
                f"Offre d'investissement : {offre}\n\n"
                "Trouve les startups pertinentes, classe-les par ordre de pertinence et explique ton classement."
            ),
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise InvestisseurMatchingAgentError(str(exc)) from exc
