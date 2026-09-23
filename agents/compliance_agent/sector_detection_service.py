"""Agent conformité — détection du secteur réglementé (service 3.3.5, étape

0). Version agentique (même conversion que healthtech_gap_analysis_
service.py) : l'agent lit lui-même le profil via son tool
lire_profil_projet (secteur déclaré + description), au lieu de recevoir ces
deux champs déjà extraits par l'appelant.

Exécution factorisée dans agents/shared/groq_runtime/react_agent_runner.py
(construction ChatGroq/create_react_agent + rotation multi-clés Groq),
partagée avec les 4 autres sous-agents de compliance_agent -- voir sa
docstring pour le raisonnement complet.

Pas de recherche vectorielle utile ici (contrairement à ai_act_service.py /
rgpd_service.py) : il ne s'agit pas d'extraire des obligations d'un corpus
légal, mais de classer un texte libre dans l'une de 2 catégories connues à
l'avance (scope volontaire, voir docstring `project_sector_detection.py`) —
le system prompt indique explicitement à l'agent de ne pas utiliser
rechercher_corpus_reglementaire/lire_diagnostics_existants pour cette tâche,
même si les 3 tools génériques lui sont passés (cohérence de pattern avec
les autres sous-agents de compliance_agent).
"""
from typing import Callable, Literal

from pydantic import BaseModel

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent

_RECURSION_LIMIT = 6

SecteurDetecte = Literal["healthtech", "fintech", "aucun"]


class SectorDetectionAgentError(ReactAgentError):
    """Échec d'appel à l'agent (LLM/Groq) ou réponse hors schéma."""


class SectorDetectionResult(BaseModel):
    secteur_detecte: SecteurDetecte
    justification: str


def detect_sector(tools: list[Callable]) -> SectorDetectionResult:
    """Classe le secteur déclaré + la description du projet en 'healthtech',

    'fintech' ou 'aucun'. Appelé uniquement par
    `sector_detection_diagnostic_service.run_detection()`, sur déclenchement
    explicite (bouton dédié côté frontend).
    """
    config = get_llm_config()["compliance_agent_sector"]["detection"]
    system_prompt = get_prompts()["compliance_agent_sector"]["system"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=SectorDetectionResult,
            task_message="Détecte le secteur réglementé (healthtech/fintech/aucun) de ce projet.",
            recursion_limit=_RECURSION_LIMIT,
        )
    except ReactAgentError as exc:
        raise SectorDetectionAgentError(str(exc)) from exc
