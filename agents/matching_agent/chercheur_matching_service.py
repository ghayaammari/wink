"""Agent de matching Recherche-Startup (EPIC-07, service 7.7.2) — trouve,
parmi les chercheurs inscrits sur Wink, ceux pertinents pour un besoin
scientifique déclaré par un entrepreneur (research_needs), classés par
ordre de pertinence avec une explication de chaque rang.

Même moteur que compliance_agent (agents/shared/groq_runtime/
react_agent_runner.py, run_react_agent) : un ChatGroq + system prompt
(agents/config/prompts.yaml, matching_agent_chercheur.system) + les tools
(construits côté backend/matching/services/chercheur_matching_tools_
service.py, fermés sur db/need — agents/ ne touche jamais la DB
directement) + response_format qui force la sortie dans
ChercheurMatchingResult.

CORRECTIF du 23/09/2026 (v3, voir chercheur_matching_tools_service.py pour
le détail complet) : le besoin est maintenant embarqué directement dans le
message de tâche (`besoin` ci-dessous), au lieu d'un tool `lire_besoin` --
un aller-retour LLM de moins, sur un budget Groq (8000 TPM/org, tier
gratuit) qui s'est avéré trop juste pour la version à 6 tools.
"""
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 15


class ChercheurMatchingAgentError(ReactAgentError):
    """Échec d'appel à l'agent (LLM/Groq) ou réponse hors schéma."""


class ChercheurMatch(BaseModel):
    researcher_profile_id: str = Field(description="Id vu via lister_chercheurs_disponibles, jamais inventé.")
    nom: str
    rang: int = Field(ge=1, description="1 = le plus pertinent, sans trou, jamais de doublon.")
    niveau_pertinence: Literal["fort", "moyen", "faible"]
    explication: str = Field(description="Concrète, citant l'info exacte utilisée -- jamais vague.")


class ChercheurMatchingResult(BaseModel):
    matches: list[ChercheurMatch] = Field(description="Seulement les chercheurs pertinents, liste vide si aucun.")
    synthese: str = Field(description="1-2 phrases sur la démarche suivie.")


def match_chercheurs(tools: list[Callable], besoin: dict) -> ChercheurMatchingResult:
    """Appelée uniquement par chercheur_matching_orchestration_service.

    run_matching(), sur déclenchement explicite (bouton "Visualiser" côté
    frontend) -- jamais automatique au dépôt du besoin, même raisonnement
    que les sous-agents compliance_agent (un vrai appel LLM+tools coûteux).

    `besoin` : dict {type_besoin, titre, description, projet: {...}} --
    construit par chercheur_matching_orchestration_service.run_matching,
    injecté tel quel dans le message de tâche (plus de tool lire_besoin,
    voir CORRECTIF v3 ci-dessus)."""
    config = get_llm_config()["matching_agent_chercheur"]["matching"]
    system_prompt = get_prompts()["matching_agent_chercheur"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=ChercheurMatchingResult,
            task_message=(
                f"Besoin scientifique : {besoin}\n\n"
                "Trouve les chercheurs pertinents, classe-les par ordre de pertinence et explique ton classement."
            ),
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise ChercheurMatchingAgentError(str(exc)) from exc
