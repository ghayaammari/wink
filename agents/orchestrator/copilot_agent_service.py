"""Agent conversationnel du copilot entrepreneur (agents/orchestrator/) --

premiere brique de l'orchestrateur prevu dans Wink_compliance_agent_recap.md
section 6.

Routage a 4 domaines : un premier appel LLM leger, sans tool, classe le
dernier message utilisateur en "reglementaire" (creation d'entreprise, voir
administrative_agent), "matching_chercheur", "matching_offres" ou
"conformite" (RGPD/AI Act/secteurs reglementes, comportement par defaut)
-- PUIS un second appel LLM, avec seulement les tools et le system prompt du
domaine choisi, produit la reponse.

Historique du perimetre matching (a lire dans l'ordre, les 2 corrections
suivantes sont contradictoires en apparence, la seconde l'emporte) :
- CORRECTIF du 25/09/2026 -- suppression du volet matching du copilot : deux
  domaines "matching"/"matching_investisseur" avaient ete ajoutes, delegues
  a deux agents conversationnels dedies (matching_copilot_service.py,
  matching_investisseur_copilot_service.py, ~390 lignes au total). Decision
  actee a l'epoque : l'entrepreneur consulte deja ces informations sur les
  pages Matching et Investissement dediees, aucun besoin reel n'aurait
  justifie de dupliquer cet acces en conversation.
- CORRECTIF du 26/09/2026 -- retour partiel sur la decision precedente, a la
  demande explicite du produit : le copilot doit rester "un copilot pour
  tout", avec une vraie delegation par domaine (meme pattern que
  "reglementaire" -> administrative_agent), plutot que de fusionner ces 2
  tools dans le toolset "conformite" (etat intermediaire du 25/09/2026 v3).
  Beaucoup plus leger que ce qui avait ete retire le 25/09/2026 : pas de
  nouveau fichier d'agent, juste 2 branches supplementaires ici meme
  (`elif domaine == "matching_chercheur"/"matching_offres"`), chacune un
  seul outil de lecture (voir chercheur_matching_tools_service.py /
  startup_offer_matching_tools_service.py pour les tools eux-memes -- ils
  vivent dans le module de l'agent de matching concerne, pas ici, meme
  respect de l'architecture par domaine que documente au 25/09/2026 v3).

Choix : classification-puis-delegation plutot qu'un seul appel avec TOUS les
tools fusionnes (y compris administratif). Un seul appel fusionne aurait ete
plus simple (le ReAct choisit deja quel tool utiliser), mais alourdit le
system prompt + la surface de tools presente a chaque tour -- directement le
probleme deja rencontre sur ce meme moteur (voir CORRECTIF du 22/09/2026
dans compliance_agent_tools_service.py, tokens/minute Groq sature a 8000
TPM/organisation). La classification, elle, est un appel a part, sans tool,
donc tres peu couteuse en tokens -- moins cher au total que d'alourdir
chaque tour de la conversation principale. Dette technique assumee : si le
routage se trompe sur un message ambigu, la reponse peut chercher dans le
mauvais domaine -- fallback sur "conformite" (comportement par defaut) en
cas d'echec de la classification elle-meme.

Les 2 domaines de matching restent volontairement en LECTURE SEULE (besoins
deja declares, recommandations deja calculees) : ils ne declenchent jamais
un nouveau calcul de matching depuis la conversation -- cette action reste
le bouton dedie de la page Matching/Investissement, plus lourde en appels
LLM qu'une simple lecture et pas adaptee a etre declenchee au fil d'un
message libre. Les 3 agents one-shot de CALCUL du matching (agents/
matching_agent/) restent entierement independants du copilot : aucune
delegation dans l'autre sens, seuls leurs RESULTATS deja persistes sont lus
ici.

Difference avec les 6 sous-agents de diagnostic/matching a tache unique :
ceux-la generent un resultat one-shot a partir d'UNE tache en une phrase
(run_react_agent). Celui-ci tient une conversation a plusieurs tours
(run_react_agent_conversation) -- l'historique complet est fourni par
l'appelant a chaque appel (voir copilot_router.py : pas de persistance de
conversation en base pour cette V1, le frontend renvoie l'historique a
chaque message).
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
DomaineAgent = Literal["reglementaire", "conformite", "matching_chercheur", "matching_offres"]


class CopilotAgentError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class CopilotResponse(BaseModel):
    reponse: str
    # None si aucune redirection n'est pertinente pour ce message (voir
    # system prompt, section "Quand rediriger vers une analyse").
    rediriger_vers: DomaineRedirection | None = None
    # Rempli par l'agent lui-meme (voir system prompt, section "Generation
    # de document telechargeable") quand l'entrepreneur demande explicitement
    # un rapport/une analyse ecrite -- non-null = "reponse" EST le contenu du
    # document (titre court ici, texte complet dans "reponse"), le frontend
    # propose alors un bouton de telechargement PDF. Seuls les domaines
    # "conformite"/"matching_chercheur"/"matching_offres" le supportent : le
    # domaine "reglementaire" (administrative_agent) garde volontairement son
    # propre schema de reponse SANS ce champ, coherent avec sa regle "ne
    # redige jamais un document juridique complet a la place de l'entrepreneur"
    # (voir administrative_agent_service.py) -- pas un oubli, une exclusion
    # deliberee tant que ce garde-fou tient.
    titre_document: str | None = None


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
    """Classe `dernier_message` en "reglementaire" ou "conformite" -- voir

    docstring de module pour le raisonnement. Ne leve jamais : un echec de
    classification (Groq indisponible, cles epuisees) retombe sur
    "conformite", le comportement par defaut, plutot que de faire echouer
    toute la reponse du copilot pour un probleme de routage interne.
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


def _repondre_domaine_simple(
    messages: list[ConversationMessage], system_prompt: str, tools: list[Callable]
) -> CopilotResponse:
    """Fabrique partagee par "conformite", "matching_chercheur" et

    "matching_offres" : les 3 utilisent le meme moteur (run_react_agent_
    conversation + CopilotResponse), seuls le system prompt et le toolset
    changent. "reglementaire" reste a part (voir answer_message) : il
    delegue a un module d'agent distinct (administrative_agent_service.py),
    pas a ce meme appel generique.
    """
    config = get_llm_config()["copilot_orchestrator"]["conversation"]

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


def answer_message(
    messages: list[ConversationMessage],
    tools_conformite: list[Callable],
    tools_reglementaire: list[Callable],
    tools_matching_chercheur: list[Callable],
    tools_matching_offres: list[Callable],
) -> CopilotResponse:
    """Repond au dernier message de `messages` en tenant compte de tout

    l'historique fourni. Appele uniquement par
    `backend/entrepreneur/services/copilot_service.py`, sur chaque message
    envoye depuis la sidebar copilot du frontend. Classe d'abord le domaine
    (voir _classifier_domaine), puis delegue au domaine choisi -- un seul
    des 4 jeux de tools est reellement utilise par appel.
    """
    domaine = _classifier_domaine(messages[-1]["content"])
    prompts = get_prompts()["copilot_orchestrator"]

    if domaine == "reglementaire":
        try:
            resultat_administratif = answer_message_administratif(messages, tools_reglementaire)
        except AdministrativeAgentError as exc:
            raise CopilotAgentError(str(exc)) from exc
        return CopilotResponse(reponse=_nettoyer_reponse(resultat_administratif.reponse), rediriger_vers=None)

    if domaine == "matching_chercheur":
        return _repondre_domaine_simple(messages, prompts["system_matching_chercheur"], tools_matching_chercheur)

    if domaine == "matching_offres":
        return _repondre_domaine_simple(messages, prompts["system_matching_offres"], tools_matching_offres)

    return _repondre_domaine_simple(messages, prompts["system"], tools_conformite)


def verifier_reponse(reponse: str, seen_chunks: list[dict]) -> VerificationAncrage | None:
    """Verifie l'ancrage de `reponse` sur `seen_chunks` (chunks reellement

    recuperes pendant ce tour, toutes domaines confondus -- voir seen_chunks
    dans compliance_agent_tools_service.py / administrative_agent_tools_
    service.py ; les tools de lecture du matching (voir_resultat_matching_
    chercheur/offres) ne peuplent jamais seen_chunks, ce ne sont pas des
    outils de recherche -- voir grounding_verification_service.py pour le
    detail du second appel LLM.

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
