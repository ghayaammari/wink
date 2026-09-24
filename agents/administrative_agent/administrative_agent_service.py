"""Agent conversationnel reglementaire (EPIC-01, agents/administrative_agent/).

Meme moteur partage que copilot_agent_service.py (run_react_agent_conversation,
agents/shared/groq_runtime/react_agent_runner.py), mais system prompt et
tools distincts (voir administrative_agent_tools_service.py) -- perimetre
administratif/reglementaire de creation d'entreprise, jamais RGPD/AI Act/
secteurs reglementes (role de compliance_agent).

Deux points d'entree utilisent ce module :
- agents/orchestrator/copilot_agent_service.py, quand le routage du copilot
  (classification du dernier message) designe le domaine "reglementaire" --
  voir sa docstring pour le raisonnement du choix classification-puis-
  delegation plutot qu'un seul appel avec tous les tools fusionnes.
- tout endpoint futur de la partie administrative de l'increment 1 qui
  aurait besoin d'un echange conversationnel sur ce meme perimetre (ex. un
  assistant sur la page roadmap) -- reutilisable tel quel, il suffit de lui
  passer un historique de messages et les tools construits par
  build_administrative_agent_tools.
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


class AdministrativeAgentError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class AdministrativeAgentResponse(BaseModel):
    reponse: str


def answer_message(messages: list[ConversationMessage], tools: list[Callable]) -> AdministrativeAgentResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni. Pas de champ `rediriger_vers` (contrairement a
    CopilotResponse) : cet agent n'a pas encore de rapport/diagnostic dedie
    vers lequel rediriger -- a ajouter si un jour un tel rapport existe pour
    le perimetre reglementaire.
    """
    config = get_llm_config()["administrative_agent"]["conversation"]
    system_prompt = get_prompts()["administrative_agent"]["system"]

    try:
        return run_react_agent_conversation(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=AdministrativeAgentResponse,
            messages=messages,
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise AdministrativeAgentError(str(exc)) from exc
