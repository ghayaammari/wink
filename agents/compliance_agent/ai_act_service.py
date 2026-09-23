"""Agent conformite -- sous-domaine AI Act (service 3.3.12). Version

agentique (meme conversion que healthtech_gap_analysis_service.py) :
l'agent lit le profil d'usage de l'IA et recherche le corpus AI Act
lui-meme, via ses tools, au lieu de recevoir profil/chunks deja prepares par
l'appelant (ai_act_diagnostic_service.py).

Exécution factorisée dans agents/shared/groq_runtime/react_agent_runner.py
(construction ChatGroq/create_react_agent + rotation multi-clés Groq),
partagée avec les 4 autres sous-agents de compliance_agent.

Difference avec le RGPD : UN SEUL appel agent produit a la fois la
classification de risque ET les obligations (voir AiActDiagnosticResult),
plutot que deux taches separees -- meme logique de reduction de cout que le
passage de l'AIPD de 5 a 2 appels (voir aipd_analysis_service.py) :
classification et obligations partagent le meme contexte (profil + corpus),
une seule tache suffit.
"""
from typing import Callable, Literal

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

# Meme raisonnement de garde-fou que healthtech_gap_analysis_service.py :
# borne le nombre de "super-steps" du graphe (agent <-> tools) pour eviter
# qu'un agent jamais satisfait de ses recherches ne boucle indefiniment.
_RECURSION_LIMIT = 15

CategorieRisqueAiAct = Literal["interdit", "haut_risque", "risque_limite", "gouvernance_gpai", "minimal"]


class AiActAgentError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class ObligationCandidate(BaseModel):
    nom: str
    description: str
    # source_id REEL d'un chunk vu via rechercher_corpus_reglementaire --
    # plus un index (contrairement a l'ancienne version) : voir
    # healthtech_gap_analysis_service.ObligationGap pour le meme
    # raisonnement.
    source_id: str | None = Field(
        default=None,
        description="source_id exact d'un chunk vu via l'outil de recherche, ou null si aucun chunk precis ne s'applique.",
    )


class AiActDiagnosticResult(BaseModel):
    categorie_risque: CategorieRisqueAiAct
    justification: str = Field(
        description=(
            "Rapport d'etude de risque complet en langage clair (plusieurs paragraphes) : "
            "contexte du projet, criteres declencheurs identifies avec leur source (chunk), "
            "raisonnement menant a la categorie retenue, implications concretes pour le porteur "
            "de projet. Jamais une simple etiquette d'une phrase."
        )
    )
    obligations: list[ObligationCandidate]


def generate_ai_act_diagnostic(tools: list[Callable]) -> AiActDiagnosticResult:
    """Diagnostic AI Act (service 3.3.12) : l'agent lit le profil d'usage de

    l'IA (lire_profil_projet) et recherche dans le corpus AI Act
    (rechercher_corpus_reglementaire, domaine 'ai_act') avant de produire la
    categorie de risque du projet ET la liste des obligations qui en
    decoulent. Jamais sans source (meme regle projet que le RGPD).

    Appele uniquement quand `ai_act_data_profile.utilise_ia` n'est pas
    `False` (voir ai_act_diagnostic_service.py) : un projet n'utilisant pas
    l'IA est classe 'minimal' par simple fait structurel, sans jamais
    solliciter ce LLM.
    """
    config = get_llm_config()["compliance_agent_ai_act"]["diagnostic"]
    system_prompt = get_prompts()["compliance_agent_ai_act"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=AiActDiagnosticResult,
            task_message=(
                "Etablis le diagnostic AI Act de ce projet : categorie de risque, "
                "rapport d'etude de risque, et obligations qui en decoulent."
            ),
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise AiActAgentError(str(exc)) from exc
