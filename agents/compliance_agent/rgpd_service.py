"""Agent conformite — sous-domaine RGPD (services 3.3.1 diagnostic, 3.3.3 DPO,

3.3.4 AIPD). Un seul agent `compliance_agent` pour tout EPIC-03 (decision
actee, voir discussion) : la vdb `content_embeddings` filtre deja par
`domaine`, un agent separe par sous-theme dupliquerait tout le pipeline
retrieval + generation pour la seule difference de filtre.

Deux styles d'implementation cohabitent volontairement dans ce fichier :

- `generate_rgpd_obligations` (3.3.1) : version agentique (LangGraph,
  memes principes que healthtech_gap_analysis_service.py) -- l'agent decide
  lui-meme, via ses tools, s'il doit lire le profil et/ou rechercher dans le
  corpus RGPD, avec quelle requete, combien de fois.
- `generate_aipd_document` / `generate_aipd_verification` (3.3.4) : restent
  sur l'ancien pattern (appel Groq direct, retrieval deja fait par
  l'appelant). Pas convertis en agent a tools : le retrieval PAR SECTION
  (voir SECTIONS_AIPD, aipd_analysis_service.py) est deja une strategie
  deterministe et deliberement geometriquement precise (chaque section a
  ses propres chunks cibles) -- il n'y a pas de decision de recherche a
  deleguer a un LLM ici, contrairement au diagnostic 3.3.1 ou l'agent
  choisit reellement quoi chercher. Documente dans
  Wink_compliance_agent_recap.md, a rediscuter si le besoin change.

Aucun acces DB dans ce fichier : les tools de generate_rgpd_obligations sont
fermes sur une Session cote backend (voir compliance_agent_tools_service.py)
et injectes ici ; les chunks de generate_aipd_document/verification sont
deja recuperes par l'appelant (aipd_analysis_service.py).
"""
import functools
import json
import os
import time
from typing import Callable

from pydantic import BaseModel, Field, ValidationError

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3


class RgpdAgentError(ReactAgentError):
    """Echec d'appel au LLM/agent ou reponse hors schema, meme apres retries."""


class SourceChunk(BaseModel):
    """Un chunk recupere par similarite dans `content_embeddings` (domaine=

    'rgpd'), passe tel quel par l'appelant -- utilise uniquement par le
    pipeline AIPD (generate_aipd_document/verification), qui reste sur
    l'ancien pattern (voir docstring module)."""

    source_id: str
    texte: str


class ObligationCandidate(BaseModel):
    nom: str
    description: str
    # source_id REEL d'un chunk vu via rechercher_corpus_reglementaire --
    # plus un index, voir healthtech_gap_analysis_service.ObligationGap pour
    # le meme raisonnement.
    source_id: str | None = Field(
        default=None,
        description="source_id exact d'un chunk vu via l'outil de recherche, ou null si aucun chunk precis ne s'applique.",
    )
    lie_a_aipd: bool = Field(
        default=False,
        description="true si cette obligation decoule d'un besoin d'AIPD (analyse d'impact), false sinon.",
    )


class ObligationsResult(BaseModel):
    obligations: list[ObligationCandidate]


class AipdAnalysisResult(BaseModel):
    """Sortie d'une section d'AIPD OU de l'AIPD verifiee/assemblee (meme forme

    dans les 2 cas, service 3.3.4) — voir generate_aipd_document() et
    generate_aipd_verification().
    """

    contenu: str


# CORRECTIF du 26/09/2026 -- 15 (valeur standard des autres agents, voir
# ai_act_service.py/administrative_agent_service.py) s'est revele trop bas
# pour ce diagnostic specifiquement : le questionnaire RGPD a 5 questions
# INDEPENDANTES (donnees sensibles, mineurs, profilage, sous-traitants,
# transfert hors UE), et un profil qui les declenche toutes force l'agent a
# faire une recherche dans le corpus par sujet -- chaque
# rechercher_corpus_reglementaire() consomme ~2 pas du graphe LangGraph
# (appel modele + appel outil), donc 5-6 sujets suffisent a depasser 15 pas
# avant que l'agent ait pu conclure (GraphRecursionError -> 502 pour
# l'entrepreneur). Aucun autre diagnostic du projet n'a autant de questions
# independantes a la fois -- ce n'est pas une regle generale a repercuter
# partout, juste ce service qui a besoin de plus de marge.
_RGPD_RECURSION_LIMIT = 30

# CORRECTIF du 26/09/2026 -- constate en pratique : meme avec des consignes
# explicites dans le prompt ("recherche chaque sujet une seule fois"),
# le modele reformule et relance des recherches sur des sujets deja
# couverts (ex: "registre des traitements article 30 rgpd" puis
# "registre des traitements obligations RGPD" quelques appels plus tard) --
# une instruction textuelle ne suffit pas a garantir ce comportement, donc
# on l'impose au niveau code plutot que de compter sur le prompt seul
# (celui-ci reste utile pour la QUALITE des recherches, juste pas pour en
# borner le NOMBRE). _MAX_RECHERCHES_CORPUS plafonne le nombre d'appels a
# rechercher_corpus_reglementaire pour CE diagnostic uniquement (5 sujets
# theoriques + marge) ; au-dela, l'outil renvoie un message qui pousse
# l'agent a conclure avec ce qu'il a deja, plutot que de continuer a
# consommer le budget de pas du graphe (et le quota Groq) sans fin.
_MAX_RECHERCHES_CORPUS = 8


def _plafonner_recherches(tools: list[Callable]) -> list[Callable]:
    """Remplace, dans `tools`, le tool rechercher_corpus_reglementaire par une

    version qui compte ses propres appels et refuse au-dela de
    _MAX_RECHERCHES_CORPUS (voir CORRECTIF ci-dessus) -- garde le meme nom
    et la meme docstring (via functools.wraps) pour que le schema d'outil
    expose au modele reste identique. Local a generate_rgpd_obligations :
    ne touche pas compliance_agent_tools_service.py, qui reste responsable
    de la recherche elle-meme, pas de sa frequence d'appel.

    `_faire_wrapper` isole la fermeture sur `outil` dans son propre appel de
    fonction -- necessaire pour eviter le piege classique des fermetures
    Python dans une boucle (toutes partageraient sinon la meme variable
    `outil`, celle de la DERNIERE iteration)."""
    compteur = {"n": 0}

    def _faire_wrapper(outil: Callable) -> Callable:
        @functools.wraps(outil)
        def wrapper(domaine: str, requete: str):
            if compteur["n"] >= _MAX_RECHERCHES_CORPUS:
                return [
                    {
                        "source_id": None,
                        "texte": (
                            "Limite de recherches atteinte pour ce diagnostic. "
                            "Conclus maintenant avec les elements deja recuperes, "
                            "ne recherche plus rien."
                        ),
                    }
                ]
            compteur["n"] += 1
            return outil(domaine, requete)

        return wrapper

    return [
        _faire_wrapper(outil) if getattr(outil, "__name__", None) == "rechercher_corpus_reglementaire" else outil
        for outil in tools
    ]


def generate_rgpd_obligations(tools: list[Callable]) -> ObligationsResult:
    """Diagnostic RGPD (service 3.3.1) : l'agent lit le profil de traitement

    de donnees (lire_profil_projet, cle "questionnaire_rgpd") et recherche
    dans le corpus RGPD (rechercher_corpus_reglementaire, domaine 'rgpd')
    avant de produire la liste des obligations applicables. Jamais sans
    source (regle projet : "aucune reponse reglementaire sans source
    verifiable") -- une liste vide est une reponse valide si aucun chunk ne
    s'applique.
    """
    config = get_llm_config()["compliance_agent_rgpd"]["diagnostic"]
    system_prompt = get_prompts()["compliance_agent_rgpd"]["system"]
    tools = _plafonner_recherches(tools)

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=ObligationsResult,
            task_message="Etablis le diagnostic RGPD (obligations applicables) pour ce projet.",
            recursion_limit=_RGPD_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise RgpdAgentError(str(exc)) from exc


# --- AIPD (3.3.4) : ancien pattern, voir docstring module ------------------


def _get_client():
    from groq import Groq

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RgpdAgentError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client, **kwargs):
    delay = _RATE_LIMIT_BASE_DELAY_SECONDS
    for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            is_rate_limit = getattr(exc, "status_code", None) == 429
            if not is_rate_limit or attempt == _RATE_LIMIT_MAX_ATTEMPTS - 1:
                raise
            time.sleep(delay)
            delay += _RATE_LIMIT_BASE_DELAY_SECONDS


def _chunks_texte(chunks: list[SourceChunk]) -> str:
    return "\n\n".join(f"[{i}] {chunk.texte}" for i, chunk in enumerate(chunks)) or "(aucun chunk disponible)"


def _call_llm_json(config: dict, prompt: str, response_model: type[BaseModel], contexte_erreur: str) -> BaseModel:
    """Appel Groq + validation JSON avec retries -- reserve au pipeline AIPD

    (generate_aipd_document/verification), voir docstring module pour
    pourquoi ces 2 fonctions restent sur l'ancien pattern."""
    client = _get_client()
    last_error: Exception | None = None
    for _ in range(config["max_retries"]):
        try:
            response = _create_completion_with_backoff(
                client,
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=config["temperature"],
            )
        except Exception as exc:
            raise RgpdAgentError(f"Echec de l'appel au LLM (Groq, {contexte_erreur}) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return response_model.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise RgpdAgentError(
        f"Le LLM n'a pas produit de JSON valide pour {contexte_erreur} apres {config['max_retries']} tentatives : {last_error}"
    )


def generate_aipd_document(profil: dict, sections: list[dict]) -> AipdAnalysisResult:
    """RAG cible par section (service 3.3.4), etape 1/2 : redige les 4

    sections de l'AIPD en un seul appel LLM, avec des chunks recuperes
    specifiquement PAR SECTION par l'appelant (voir SECTIONS_AIPD dans
    aipd_analysis_service.py) -- retrieval deterministe, pas convertie en
    agent a tools (voir docstring module).

    `sections` : liste ordonnee de dicts {"titre", "consignes", "chunks"}
    (chunks = list[SourceChunk] deja filtres par section par l'appelant).
    """
    config = get_llm_config()["compliance_agent_rgpd"]["aipd"]
    prompt_template = get_prompts()["compliance_agent_rgpd"]["aipd_document"]
    sections_bloc = "\n\n".join(
        f"### {section['titre']}\n"
        f"Consignes pour cette section : {section['consignes']}\n"
        f"Chunks pertinents pour cette section :\n{_chunks_texte(section['chunks'])}"
        for section in sections
    )
    prompt = prompt_template.format(
        sections_bloc=sections_bloc,
        profil_json=json.dumps(profil, ensure_ascii=False),
        schema_json=json.dumps(AipdAnalysisResult.model_json_schema()),
    )
    return _call_llm_json(config, prompt, AipdAnalysisResult, "l'analyse d'impact (AIPD)")


def generate_aipd_verification(document_assemble: str, chunks: list[SourceChunk]) -> AipdAnalysisResult:
    """RAG cible par section (service 3.3.4), etape 2/2 : relit le document

    assemble et reformule toute affirmation non justifiee par les chunks
    fournis -- ajoute le 18/09/2026 suite a une AIPD ayant cite un mecanisme
    juridique perime genere par un simple appel LLM sans etape de
    verification."""
    config = get_llm_config()["compliance_agent_rgpd"]["aipd"]
    prompt_template = get_prompts()["compliance_agent_rgpd"]["aipd_verification"]
    prompt = prompt_template.format(
        document_assemble=document_assemble,
        chunks_texte=_chunks_texte(chunks),
        schema_json=json.dumps(AipdAnalysisResult.model_json_schema()),
    )
    return _call_llm_json(config, prompt, AipdAnalysisResult, "la verification de l'AIPD")
