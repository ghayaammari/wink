"""Agent conversationnel du copilot entrepreneur (agents/orchestrator/) --

premiere brique de l'orchestrateur prevu dans Wink_compliance_agent_recap.md
section 6. Pour l'instant, un seul domaine agent existe (compliance_agent),
donc ce module ne "route" pas encore entre plusieurs agents : il repond
directement aux questions de conformite avec les memes 3 tools deja utilises
par les 5 sous-agents de compliance_agent (voir
backend/entrepreneur/services/compliance_agent_tools_service.py,
build_compliance_agent_tools -- reutilise tel quel, aucun nouveau tool
introduit ici).

Quand un 2e agent de domaine existera (ex: administrative_agent), ce fichier
sera le point naturel pour ajouter une vraie decision de routage (quel(s)
agent(s) appeler selon la question) -- pas anticipe maintenant, pas de
structure de routage a construire pour un seul agent (voir "reste sobre",
instructions du projet).

Difference avec les 5 sous-agents de diagnostic : ceux-la generent un
resultat one-shot a partir d'UNE tache en une phrase (run_react_agent).
Celui-ci tient une conversation a plusieurs tours (run_react_agent_
conversation) -- l'historique complet est fourni par l'appelant a chaque
appel (voir copilot_router.py : pas de persistance de conversation en base
pour cette V1, le frontend renvoie l'historique a chaque message).
"""
import logging
import re
from typing import Callable, Literal

from pydantic import BaseModel

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.grounding_verification_service import VerificationAncrage, verifier_ancrage
from agents.shared.groq_runtime.react_agent_runner import (
    ConversationMessage,
    ReactAgentError,
    run_react_agent_conversation,
)

logger = logging.getLogger(__name__)

_RECURSION_LIMIT = 15

DomaineRedirection = Literal["rgpd", "ai-act", "secteur"]


class CopilotAgentError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class CopilotResponse(BaseModel):
    reponse: str
    # None si aucune redirection n'est pertinente pour ce message (voir
    # system prompt, section "Quand rediriger vers une analyse").
    rediriger_vers: DomaineRedirection | None = None


_GRAS_MARKDOWN_RE = re.compile(r"\*\*(.+?)\*\*")


def _nettoyer_reponse(texte: str) -> str:
    """Filet de securite anti-Markdown residuel.

    Le system prompt interdit deja le Markdown (voir prompts.yaml), mais les
    modeles open-weight en sortie JSON stricte (response_format=CopilotResponse)
    melangent parfois l'echappement JSON et le formatage Markdown : ils tapent
    litteralement les 2 caracteres "\\n" au lieu d'un vrai saut de ligne, ou
    laissent trainer des "**gras**". Le frontend affiche le texte brut, sans
    rendu Markdown (whitespace-pre-wrap, voir CopilotPage.tsx), donc on
    normalise ici plutot que de faire reposer la lisibilite entierement sur
    la discipline du modele.
    """
    texte = texte.replace("\\n", "\n").replace("\\t", "\t")
    return _GRAS_MARKDOWN_RE.sub(r"\1", texte)


def answer_message(messages: list[ConversationMessage], tools: list[Callable]) -> CopilotResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni. Appele uniquement par
    `backend/entrepreneur/services/copilot_service.py`, sur chaque message
    envoye depuis la sidebar copilot du frontend.
    """
    config = get_llm_config()["copilot_orchestrator"]["conversation"]
    system_prompt = get_prompts()["copilot_orchestrator"]["system"]

    try:
        resultat = run_react_agent_conversation(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=CopilotResponse,
            messages=messages,
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise CopilotAgentError(str(exc)) from exc

    resultat.reponse = _nettoyer_reponse(resultat.reponse)
    return resultat


def verifier_reponse(reponse: str, seen_chunks: list[dict]) -> VerificationAncrage | None:
    """Verifie l'ancrage de `reponse` sur `seen_chunks` (chunks reellement

    recuperes pendant ce tour, voir seen_chunks dans
    compliance_agent_tools_service.py) -- voir grounding_verification_service.py
    pour le detail du second appel LLM.

    Renvoie None dans deux cas bien distincts, volontairement confondus ici
    car le frontend n'a pas besoin de les distinguer (voir
    CopilotMessageResponse.ancrage_verifie) :
    - `seen_chunks` vide : l'agent n'a appele aucun outil de recherche
      pendant ce tour (question generale), rien a verifier.
    - Echec de l'appel de verification lui-meme (Groq indisponible...) : un
      echec de la verification ne doit JAMAIS faire echouer la reponse
      principale deja produite, juste la laisser non annotee -- logge en
      warning pour audit, pas remonte comme erreur a l'appelant.
    """
    if not seen_chunks:
        return None
    try:
        return verifier_ancrage(reponse, seen_chunks)
    except Exception:
        logger.warning("Echec de la verification d'ancrage du copilot (non bloquant).", exc_info=True)
        return None
