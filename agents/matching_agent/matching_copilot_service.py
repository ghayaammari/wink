"""Agent conversationnel du matching chercheur (agents/matching_agent/),

volet copilot -- distinct de chercheur_matching_service.py (agent one-shot
qui CALCULE un matching pour un besoin precis, declenche par le bouton
dedie). Celui-ci ne fait que REPONDRE aux questions de l'entrepreneur sur
ses besoins deja declares et les recommandations deja calculees (voir
matching_copilot_tools_service.py) -- jamais de calcul de matching depuis
une conversation libre.

Meme moteur partage que copilot_agent_service.py/administrative_agent_
service.py (run_react_agent_conversation). Point d'entree unique pour
l'instant : agents/orchestrator/copilot_agent_service.py, quand le routage
designe le domaine "matching".
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


class MatchingCopilotError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class MatchingCopilotResponse(BaseModel):
    reponse: str


def answer_message(messages: list[ConversationMessage], tools: list[Callable]) -> MatchingCopilotResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni -- meme contrat que les autres agents conversationnels
    du copilot (voir administrative_agent_service.py::answer_message).
    """
    config = get_llm_config()["matching_copilot"]["conversation"]
    system_prompt = get_prompts()["matching_copilot"]["system"]

    try:
        return run_react_agent_conversation(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=MatchingCopilotResponse,
            messages=messages,
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise MatchingCopilotError(str(exc)) from exc
