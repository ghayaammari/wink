"""Agent conversationnel du copilot entrepreneur (agents/orchestrator/) --

premiere brique de l'orchestrateur prevu dans Wink_compliance_agent_recap.md
section 6.

Routage a 4 domaines desormais (avant : 3, sans le volet investisseur) : un
premier appel LLM leger, sans tool, classe le dernier message utilisateur en
"reglementaire" (creation d'entreprise, voir administrative_agent),
"conformite" (RGPD/AI Act/secteurs reglementes, comportement historique),
"matching" (besoins scientifiques deja declares + recommandations de
chercheurs deja calculees, voir matching_copilot) ou "matching_investisseur"
(investisseurs ayant deja marque un interet pour ce projet, voir
matching_investisseur_copilot -- sens INVERSE de "matching", Investisseur ->
Startup plutot qu'Entrepreneur -> Chercheur) -- PUIS un second appel LLM,
avec seulement les tools et le system prompt du domaine choisi, produit la
reponse.

Choix : classification-puis-delegation plutot qu'un seul appel avec TOUS les
tools fusionnes. Un seul appel fusionne aurait ete plus simple (le ReAct
choisit deja quel tool utiliser), mais double (desormais triple) le system
prompt + la surface de tools presente a chaque tour -- directement le
probleme deja rencontre sur ce meme moteur (voir CORRECTIF du 22/09/2026
dans compliance_agent_tools_service.py, tokens/minute Groq sature a 8000
TPM/organisation). La classification, elle, est un appel a part, sans tool,
donc tres peu couteuse en tokens -- moins cher au total que d'alourdir
chaque tour de la conversation principale. Dette technique assumee : si le
routage se trompe sur un message ambigu, la reponse peut chercher dans le
mauvais domaine -- fallback sur "conformite" (comportement d'avant tout
routage) en cas d'echec de la classification elle-meme.

Le matching integre ici reste volontairement en LECTURE SEULE (besoins deja
declares, recommandations deja calculees, voir matching_copilot_tools_
service.py) : il ne declenche jamais un nouveau calcul de matching depuis la
conversation -- cette action reste le bouton dedie de la page Matching
(chercheur_matching_orchestration_service.run_matching), plus lourde en
appels LLM qu'une simple lecture et pas adaptee a etre declenchee au fil
d'un message libre.

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

from agents.administrative_agent.administrative_agent_service import (
    AdministrativeAgentError,
    answer_message as answer_message_administratif,
)
from agents.config.loader import get_llm_config, get_prompts
from agents.matching_agent.matching_copilot_service import (
    MatchingCopilotError,
    answer_message as answer_message_matching,
)
from agents.matching_agent.matching_investisseur_copilot_service import (
    MatchingInvestisseurCopilotError,
    answer_message as answer_message_matching_investisseur,
)
from agents.shared.groq_runtime.grounding_verification_service import VerificationAncrage, verifier_ancrage
from agents.shared.groq_runtime.react_agent_runner import (
    ConversationMessage,
    ReactAgentError,
    run_react_agent,
    run_react_agent_conversation,
)

logger = logging.getLogger(__name__)

_RECURSION_LIMIT = 15
_RECURSION_LIMIT_ROUTAGE = 3

DomaineRedirection = Literal["rgpd", "ai-act", "secteur"]
DomaineAgent = Literal["reglementaire", "conformite", "matching", "matching_investisseur"]


class CopilotAgentError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class CopilotResponse(BaseModel):
    reponse: str
    # None si aucune redirection n'est pertinente pour ce message (voir
    # system prompt, section "Quand rediriger vers une analyse").
    rediriger_vers: DomaineRedirection | None = None


class _DomaineClassification(BaseModel):
    domaine: DomaineAgent


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


def _classifier_domaine(dernier_message: str) -> DomaineAgent:
    """Classe `dernier_message` en "reglementaire", "conformite", "matching"

    ou "matching_investisseur" -- voir docstring de module pour le raisonnement. Ne leve
    jamais : un echec de classification (Groq indisponible, cles epuisees)
    retombe sur "conformite", le comportement d'avant tout routage, plutot
    que de faire echouer toute la reponse du copilot pour un probleme de
    routage interne.
    """
    config = get_llm_config()["copilot_orchestrator"]["routage"]
    system_prompt = get_prompts()["copilot_orchestrator"]["routage_system"]

    try:
        resultat = run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=[],
            response_format=_DomaineClassification,
            task_message=dernier_message,
            recursion_limit=_RECURSION_LIMIT_ROUTAGE,
        )
        logger.info("Copilot -- routage vers l'agent '%s' pour ce message.", resultat.domaine)
        return resultat.domaine
    except ReactAgentError:
        logger.warning("Echec du routage du copilot, repli sur 'conformite'.", exc_info=True)
        return "conformite"


def answer_message(
    messages: list[ConversationMessage],
    tools_conformite: list[Callable],
    tools_reglementaire: list[Callable],
    tools_matching: list[Callable],
    tools_matching_investisseur: list[Callable],
) -> CopilotResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni. Appele uniquement par
    `backend/entrepreneur/services/copilot_service.py`, sur chaque message
    envoye depuis la sidebar copilot du frontend. Classe d'abord le domaine
    (voir _classifier_domaine), puis delegue au domaine choisi -- un seul
    des 4 jeux de tools est reellement utilise par appel.
    """
    domaine = _classifier_domaine(messages[-1]["content"])

    if domaine == "reglementaire":
        try:
            resultat_administratif = answer_message_administratif(messages, tools_reglementaire)
        except AdministrativeAgentError as exc:
            raise CopilotAgentError(str(exc)) from exc
        return CopilotResponse(reponse=_nettoyer_reponse(resultat_administratif.reponse), rediriger_vers=None)

    if domaine == "matching":
        try:
            resultat_matching = answer_message_matching(messages, tools_matching)
        except MatchingCopilotError as exc:
            raise CopilotAgentError(str(exc)) from exc
        return CopilotResponse(reponse=_nettoyer_reponse(resultat_matching.reponse), rediriger_vers=None)

    if domaine == "matching_investisseur":
        try:
            resultat_matching_investisseur = answer_message_matching_investisseur(
                messages, tools_matching_investisseur
            )
        except MatchingInvestisseurCopilotError as exc:
            raise CopilotAgentError(str(exc)) from exc
        return CopilotResponse(
            reponse=_nettoyer_reponse(resultat_matching_investisseur.reponse), rediriger_vers=None
        )

    config = get_llm_config()["copilot_orchestrator"]["conversation"]
    system_prompt = get_prompts()["copilot_orchestrator"]["system"]

    try:
        resultat = run_react_agent_conversation(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools_conformite,
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

    recuperes pendant ce tour, toutes domaines confondus -- voir seen_chunks
    dans compliance_agent_tools_service.py / administrative_agent_tools_
    service.py ; matching_copilot ne peuple jamais seen_chunks, voir sa
    docstring) -- voir grounding_verification_service.py pour le detail du
    second appel LLM.

    Renvoie None dans deux cas bien distincts, volontairement confondus ici
    car le frontend n'a pas besoin de les distinguer (voir
    CopilotMessageResponse.ancrage_verifie) :
    - `seen_chunks` vide : l'agent n'a appele aucun outil de recherche
      pendant ce tour (question generale, ou domaine matching), rien a
      verifier.
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
