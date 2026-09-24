"""Agent conversationnel du matching investisseur (agents/matching_agent/),

volet copilot -- sens INVERSE de matching_copilot_service.py : celui-la lit
cote entrepreneur ses propres besoins scientifiques + recommandations de
chercheurs (entrepreneur -> chercheur) ; celui-ci lit les investisseurs qui
ont marque un interet pour LE PROJET de l'entrepreneur connecte
(Investisseur -> Startup, voir matching_investisseur_copilot_tools_
service.py). Distinct de investisseur_matching_service.py (agent one-shot
qui CALCULE un matching pour une offre, declenche par le bouton
"Visualiser" cote investisseur) : celui-ci ne fait que REPONDRE aux
questions de l'entrepreneur sur les interets deja manifestes, jamais de
calcul depuis une conversation libre.

Meme moteur partage que les autres agents conversationnels du copilot
(run_react_agent_conversation). Point d'entree unique : agents/orchestrator/
copilot_agent_service.py, domaine "matching_investisseur".
"""
from typing import Callable

from pydantic import BaseModel

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import (
    ConversationMessage,
    ReactAgentError,
    run_react_agent_conversation,
)

_RECURSION_LIMIT = 15


class MatchingInvestisseurCopilotError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class MatchingInvestisseurCopilotResponse(BaseModel):
    reponse: str


def answer_message(messages: list[ConversationMessage], tools: list[Callable]) -> MatchingInvestisseurCopilotResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni -- meme contrat que les autres agents conversationnels
    du copilot (voir matching_copilot_service.py::answer_message)."""
    config = get_llm_config()["matching_investisseur_copilot"]["conversation"]
    system_prompt = get_prompts()["matching_investisseur_copilot"]["system"]

    try:
        return run_react_agent_conversation(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=MatchingInvestisseurCopilotResponse,
            messages=messages,
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise MatchingInvestisseurCopilotError(str(exc)) from exc
