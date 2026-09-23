"""Execution partagee des agents LangGraph a tools sur Groq (pattern ReAct).

Factorise le boilerplate identique aux 5 sous-agents de compliance_agent
(sector_detection, rgpd, ai_act, healthtech_gap, fintech_gap) : construire un
ChatGroq, l'enregistrer dans create_react_agent avec les tools et le
response_format, invoquer, extraire structured_response -- une 6e copie
quasi identique n'a plus de sens au moment d'ajouter administrative_agent/
contract_agent (voir docstring de key_pool.py pour le raisonnement complet
sur pourquoi ce chantier est fait maintenant plutot que reporte).

Ajoute aussi la rotation multi-cles (key_pool.py) : sur une erreur 429, la
cle utilisee est mise en cooldown et l'agent entier est reconstruit et
relance avec la cle suivante disponible -- rotation au niveau de l'appel
complet (pas de la requete HTTP individuelle), plus simple et suffisant tant
que chaque generation reste un seul run d'agent de bout en bout.

Deux points d'entree publics, meme moteur commun (_invoke_with_rotation) :
- run_react_agent(task_message=...) : une seule tache en une phrase, une
  seule fois -- ce que font les 5 sous-agents de compliance_agent (chacun
  genere un resultat, pas de conversation).
- run_react_agent_conversation(messages=...) : un historique complet
  (plusieurs tours utilisateur/assistant), ajoute pour l'orchestrateur/
  copilot (agents/orchestrator/) qui a besoin de memoire de conversation --
  contrairement aux 5 sous-agents, une seule tache ne suffit pas a modeliser
  un dialogue.

Difference de strategie de sortie structuree entre les deux : run_react_agent
(5 sous-agents) laisse `create_react_agent` utiliser le defaut de ChatGroq
(`with_structured_output(schema)` -> method="function_calling", un tool
force en fin de boucle). run_react_agent_conversation force method=
"json_schema" (_ChatGroqJsonSchemaOutput ci-dessous) : sur un tour de
conversation ou l'agent ne fait AUCUN appel outil (question generale sans
besoin de recherche, ex. "que veut dire RGPD ?"), Groq peut renvoyer sur le
tool force "Tool choice is required, but model did not call a tool" (400) --
le modele a deja produit sa reponse en texte libre et n'a pas de raison
d'emettre un appel outil supplementaire. json_schema evite ce mode force
(sortie JSON contrainte nativement par l'API Groq, sans tool_choice) ; les 5
sous-agents ne sont pas touches par ce changement car ils appellent presque
toujours au moins un outil avant de conclure, donc n'ont jamais declenche ce
bug en pratique -- mais garder function_calling pour eux plutot que de
generaliser json_schema partout evite de changer un comportement deja
verifie sans necessite (voir "reste sobre", instructions du projet).

Journalise aussi chaque appel d'outil fait par l'agent (_log_tool_calls) --
seul moyen actuel de verifier qu'une reponse s'appuie sur des chunks
reellement recuperes par rechercher_corpus_reglementaire plutot que sur la
connaissance interne du modele : pas de verification automatique
(entailment, ex. un second appel LLM qui confronte chaque affirmation de la
reponse aux chunks recuperes) pour l'instant -- ce log est une aide manuelle
au debug/audit, pas une garantie. Avant cet ajout, aucun agent (les 5 sous-
agents inclus) ne laissait de trace des outils utilises nulle part.
"""
from __future__ import annotations

import logging
from typing import Callable, Literal, TypedDict, TypeVar

from pydantic import BaseModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from .key_pool import GroqKeyPool, get_groq_api_keys

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class ReactAgentError(Exception):
    """Echec d'appel a l'agent (Groq/LangGraph), y compris apres epuisement

    de toutes les cles disponibles (toutes en cooldown 429), ou reponse hors
    schema (structured_response absent)."""


class _ChatGroqJsonSchemaOutput(ChatGroq):
    """ChatGroq dont with_structured_output() utilise method="json_schema"

    par defaut au lieu de "function_calling" (comportement natif de
    ChatGroq) -- voir docstring de module ci-dessus pour la raison. strict=
    True active la decodage contraint cote Groq (garanti conforme au schema),
    supporte uniquement par openai/gpt-oss-20b et openai/gpt-oss-120b (seul
    modele utilise par Wink a ce jour, voir agents/config/llm_config.yaml) --
    si un modele sans ce support est configure un jour pour un appel
    utilisant cette classe, Groq ignore silencieusement `strict` plutot que
    d'echouer (comportement documente par langchain-groq).
    """

    def with_structured_output(self, schema=None, **kwargs):
        kwargs.setdefault("method", "json_schema")
        kwargs.setdefault("strict", True)
        return super().with_structured_output(schema, **kwargs)


_pool: GroqKeyPool | None = None


def _get_pool() -> GroqKeyPool:
    global _pool
    if _pool is None:
        keys = get_groq_api_keys()
        if not keys:
            raise ReactAgentError("Aucune cle Groq trouvee (GROQ_API_KEY manquant dans .env).")
        _pool = GroqKeyPool(keys)
    return _pool


def _is_rate_limit_error(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) == 429:
        return True
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 429


# CORRECTIF du 22/09/2026 -- constate en pratique sur compliance_agent_secnumcloud,
# deux fois de suite sous des formes differentes ("leer_profil_projet<|channel|>
# commentary" puis "leer_profil_projet") : rate de decodage isole du modele
# (openai/gpt-oss-120b, Groq) qui deforme legerement le nom d'un tool reel --
# jamais un 429 (donc jamais un signal de rotation de cle, voir _is_rate_limit_error),
# la cle en cours suffit generalement au retry suivant. Groq renvoie ça en 400
# avec code 'tool_use_failed' -- detection par le message plutot que par un
# attribut d'exception precis (le type d'exception leve par le client Groq
# n'est pas garanti stable dans le temps, contrairement au code qu'il transporte).
_TOOL_USE_ERROR_MAX_ATTEMPTS = 3


def _is_tool_use_error(exc: Exception) -> bool:
    return "tool_use_failed" in str(exc)


def _invoke_agent(agent, messages: list[ConversationMessage], recursion_limit: int):
    """Invoque l'agent une fois, avec un retry immediat (meme cle, pas de

    delai -- ce n'est pas un rate limit) pour un rate de tool-calling isole
    du modele (voir _is_tool_use_error). Toute autre exception (dont un 429,
    gere par l'appelant) remonte immediatement sans retry ici."""
    last_error: Exception | None = None
    for attempt in range(_TOOL_USE_ERROR_MAX_ATTEMPTS):
        try:
            return agent.invoke({"messages": messages}, config={"recursion_limit": recursion_limit})
        except Exception as exc:
            if _is_tool_use_error(exc) and attempt < _TOOL_USE_ERROR_MAX_ATTEMPTS - 1:
                last_error = exc
                logger.warning(
                    "Rate de tool-calling du modele (tentative %d/%d), retry immediat : %s",
                    attempt + 1,
                    _TOOL_USE_ERROR_MAX_ATTEMPTS,
                    exc,
                )
                continue
            raise
    raise last_error  # pragma: no cover -- inatteignable, la boucle renvoie ou leve toujours


def _log_tool_calls(messages: list[BaseMessage]) -> None:
    """Journalise nom+arguments de chaque outil appele et un extrait de son

    resultat (voir docstring de module) -- appele apres chaque run reussi,
    quel que soit l'agent (5 sous-agents + copilot), tous passent par
    _invoke_with_rotation.
    """
    calls_by_id: dict[str, dict] = {}
    for message in messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            for call in message.tool_calls:
                calls_by_id[call["id"]] = call

    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        call = calls_by_id.get(message.tool_call_id, {})
        nom = call.get("name", "?")
        args = call.get("args", {})
        contenu = str(message.content)
        apercu = contenu[:300] + ("..." if len(contenu) > 300 else "")
        logger.info("Outil appele : %s(%s) -> %s", nom, args, apercu)


def _invoke_with_rotation(
    *,
    model: str,
    temperature: float,
    system_prompt: str,
    tools: list[Callable],
    response_format: type[T],
    messages: list[ConversationMessage],
    recursion_limit: int,
    use_json_schema_output: bool = False,
) -> T:
    """Coeur partage par run_react_agent/run_react_agent_conversation --

    seule la construction de `messages` differe entre les deux (une tache
    unique vs un historique complet), tout le reste (pool de cles, rotation
    429, extraction de structured_response) est identique. `use_json_schema_
    output` bascule sur _ChatGroqJsonSchemaOutput (voir docstring de module)
    -- False par defaut pour ne rien changer aux 5 sous-agents existants.
    """
    pool = _get_pool()
    last_error: Exception | None = None
    llm_class = _ChatGroqJsonSchemaOutput if use_json_schema_output else ChatGroq

    for _ in range(pool.size):
        api_key = pool.acquire()
        # CORRECTIF du 22/09/2026 -- max_retries=0 explicite, indispensable
        # pour que la rotation de cles (pool.cooldown ci-dessous) serve a
        # quelque chose : sans ça, le client Groq absorbe lui-meme chaque 429
        # avec SA PROPRE attente (backoff croissant, jusqu'a 45-46s constate
        # en pratique) sur la MEME cle, avant meme qu'une exception ne
        # remonte jusqu'ici -- la rotation vers une autre cle du pool n'etait
        # alors jamais declenchee, meme avec plusieurs cles configurees
        # (constate le 22/09/2026 : le meme blocage de plusieurs minutes est
        # revenu a l'identique juste apres l'ajout de GROQ_API_KEY_2/_3).
        # Avec max_retries=0, un 429 remonte immediatement en exception, geree
        # par notre propre boucle (cooldown 60s de la cle + cle suivante du
        # pool) -- beaucoup plus rapide des qu'au moins une autre cle est
        # disponible. Le "max_retries" de llm_config.yaml n'est pas utilise
        # ici (dette technique deja documentee) : il resterait de toute facon
        # en conflit avec ce choix si on le branchait tel quel.
        llm = llm_class(model=model, temperature=temperature, api_key=api_key, max_retries=0)
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            response_format=response_format,
        )
        try:
            state = _invoke_agent(agent, messages, recursion_limit)
        except Exception as exc:
            if _is_rate_limit_error(exc):
                pool.cooldown(api_key)
                last_error = exc
                continue
            raise ReactAgentError(f"Echec de l'appel a l'agent (Groq/LangGraph) : {exc}") from exc

        _log_tool_calls(state.get("messages", []))
        structured = state.get("structured_response")
        if structured is None:
            raise ReactAgentError("L'agent n'a pas produit de reponse structuree (structured_response absent).")
        return structured

    raise ReactAgentError(
        f"Toutes les cles Groq disponibles ({pool.size}) sont en cooldown (429 repete) : {last_error}"
    )


def run_react_agent(
    *,
    model: str,
    temperature: float,
    system_prompt: str,
    tools: list[Callable],
    response_format: type[T],
    task_message: str,
    recursion_limit: int,
) -> T:
    """Construit et execute un agent LangGraph ReAct pour UNE tache unique

    (pas de conversation) -- voir chaque sous-agent de compliance_agent pour
    son system_prompt/tools/response_format propres.

    Leve ReactAgentError si toutes les cles sont epuisees (429 repete), si
    l'appel echoue pour une autre raison, ou si l'agent ne produit pas de
    structured_response valide.
    """
    return _invoke_with_rotation(
        model=model,
        temperature=temperature,
        system_prompt=system_prompt,
        tools=tools,
        response_format=response_format,
        messages=[{"role": "user", "content": task_message}],
        recursion_limit=recursion_limit,
    )


def run_react_agent_conversation(
    *,
    model: str,
    temperature: float,
    system_prompt: str,
    tools: list[Callable],
    response_format: type[T],
    messages: list[ConversationMessage],
    recursion_limit: int,
) -> T:
    """Meme moteur que run_react_agent, mais pour un historique de

    conversation complet (copilot/orchestrateur) plutot qu'une tache unique.
    `messages` est l'historique tel que renvoye par le frontend a chaque
    appel (voir copilot_router.py : pas de persistance cote backend pour
    cette V1, le frontend renvoie tout l'historique a chaque message).

    use_json_schema_output=True (contrairement a run_react_agent) : un tour
    de conversation libre peut legitimement ne declencher aucun outil (ex.
    "que veut dire RGPD ?", "bonjour") -- voir docstring de module pour
    pourquoi le mode par defaut de ChatGroq echoue alors avec 400 "Tool
    choice is required, but model did not call a tool".
    """
    if not messages:
        raise ValueError("run_react_agent_conversation necessite au moins un message.")
    return _invoke_with_rotation(
        model=model,
        temperature=temperature,
        system_prompt=system_prompt,
        tools=tools,
        response_format=response_format,
        messages=messages,
        recursion_limit=recursion_limit,
        use_json_schema_output=True,
    )
