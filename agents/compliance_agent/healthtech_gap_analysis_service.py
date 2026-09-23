"""Agent conformite -- generation du diagnostic d'ecart HealthTech (service

3.3.6), version agentique : pilote de la conversion du compliance_agent vers
un raisonnement autonome a tools. Contrairement a l'ancienne version (un
seul appel JSON, RAG deja effectue par l'appelant), l'agent decide lui-meme,
via ses tools, s'il doit consulter le profil du projet et/ou rechercher dans
le corpus MDR -- et peut relancer une recherche avec une requete reformulee
s'il juge les premiers resultats insuffisants.

Exécution factorisée dans agents/shared/groq_runtime/react_agent_runner.py
(construction ChatGroq/create_react_agent + rotation multi-clés Groq),
partagée avec les 4 autres sous-agents de compliance_agent.

Toujours aucun acces DB ici : les tools passes en parametre (voir
backend/entrepreneur/services/compliance_agent_tools_service.py) sont de
simples fonctions Python fermees sur une Session -- ce module ne connait
jamais SQLAlchemy ni FastAPI.
"""
from typing import Callable

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 15


class HealthtechGapAnalysisError(ReactAgentError):
    """Echec d'appel a l'agent (LLM/Groq) ou reponse hors schema."""


class ObligationGap(BaseModel):
    nom: str
    description: str
    # source_id REEL d'un chunk vu via l'outil rechercher_corpus_reglementaire
    # -- plus un index (contrairement a l'ancienne version) : l'agent peut
    # appeler cet outil plusieurs fois avec des requetes differentes, un
    # index seul n'aurait plus de sens univoque d'un appel a l'autre.
    source_id: str | None = Field(
        default=None,
        description="source_id exact d'un chunk vu via l'outil de recherche, ou null si aucun chunk precis ne s'applique.",
    )


class GapAnalysisResult(BaseModel):
    obligations: list[ObligationGap]
    justification: str


def generate_gap_analysis(
    chapitre_titre: str, requete_semantique_suggeree: str, tools: list[Callable]
) -> GapAnalysisResult:
    """Diagnostic d'ecart (service 3.3.6), un chapitre a la fois -- l'agent

    decide lui-meme (via `tools`, voir build_compliance_agent_tools) s'il
    doit lire le profil/la classification du projet et rechercher dans le
    corpus MDR, avec quelle requete (peut partir de
    `requete_semantique_suggeree`, deja concue par chapitre dans
    healthtech_gap_analysis_chapitres.py, ou la reformuler / chercher a
    nouveau si les premiers resultats sont insuffisants). Jamais sans
    source (meme regle projet que l'ancienne version) : le system prompt
    interdit d'inventer une obligation non justifiee par un chunk reellement
    vu via l'outil de recherche pendant cette tache -- une liste vide est
    une reponse valide si rien ne s'applique.
    """
    config = get_llm_config()["compliance_agent_healthtech_gap"]["diagnostic"]
    system_prompt = get_prompts()["compliance_agent_healthtech_gap"]["system"]

    tache = (
        f"Chapitre a traiter : {chapitre_titre}\n\n"
        "Requete de recherche suggeree pour ce chapitre (tu peux la "
        f"reformuler ou chercher a nouveau si besoin) : {requete_semantique_suggeree}\n\n"
        "Consulte le profil du projet et recherche dans le corpus MDR "
        "(domaine 'secteur_healthtech') avant de repondre."
    )

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=GapAnalysisResult,
            task_message=tache,
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise HealthtechGapAnalysisError(str(exc)) from exc
