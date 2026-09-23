"""Agent conformité — génération du diagnostic d'écart FinTech (service

3.3.6), UN SEUL bloc (pas de découpage en chapitres, contrairement à
healthtech_gap_analysis_service.py — voir docstring de
project_fintech_gap_analysis.py). Version agentique (même conversion que
healthtech_gap_analysis_service.py) : l'agent lit le type d'agrément et
recherche le corpus lui-même, via ses tools, au lieu de recevoir ces
éléments déjà préparés par l'appelant.

Exécution factorisée dans agents/shared/groq_runtime/react_agent_runner.py
(construction ChatGroq/create_react_agent + rotation multi-clés Groq),
partagée avec les 4 autres sous-agents de compliance_agent.
"""
from typing import Callable

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 15


class FintechGapAnalysisError(ReactAgentError):
    """Échec d'appel à l'agent (LLM/Groq) ou réponse hors schéma."""


class ObligationGap(BaseModel):
    nom: str
    description: str
    source_id: str | None = Field(
        default=None,
        description="source_id exact d'un chunk vu via l'outil de recherche, ou null si aucun chunk precis ne s'applique.",
    )


class GapAnalysisResult(BaseModel):
    obligations: list[ObligationGap]
    justification: str


def generate_gap_analysis(tools: list[Callable]) -> GapAnalysisResult:
    """Diagnostic d'écart (service 3.3.6), bloc FinTech unique. L'agent lit

    le type d'agrément via lire_profil_projet (les obligations varient
    selon le type d'agrément, ex: exigences de fonds propres renforcées pour
    un agrément classique) et recherche dans le corpus FinTech via
    rechercher_corpus_reglementaire (domaine 'secteur_fintech'). Jamais sans
    source (même règle projet que rgpd_service.py) : une liste vide est une
    réponse valide si aucun chunk ne s'applique.
    """
    config = get_llm_config()["compliance_agent_fintech_gap"]["diagnostic"]
    system_prompt = get_prompts()["compliance_agent_fintech_gap"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=GapAnalysisResult,
            task_message="Etablis le diagnostic d'ecart FinTech (obligations applicables) pour ce projet.",
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise FintechGapAnalysisError(str(exc)) from exc
