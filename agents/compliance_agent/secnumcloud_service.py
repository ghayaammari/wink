"""Agent conformite — sous-domaine SecNumCloud (service 3.3.11). Meme agent

`compliance_agent` que rgpd_service.py/ai_act_service.py/etc (EPIC-03), pas
un agent separe -- meme decision actee que pour les autres sous-domaines.

Version agentique (agentic RAG, comme rgpd_service.generate_rgpd_obligations) :
l'agent decide lui-meme, via ses tools, quoi rechercher dans le corpus
SecNumCloud (domaine 'certification_secnumcloud') et s'il doit lire le profil
du projet, avant de produire a la fois les etapes du parcours (ordonnees) ET
une estimation delai/cout -- un seul appel agent pour les deux (voir
docstring de compliance_agent_secnumcloud.parcours dans prompts.yaml).

Aucun acces DB ici : les tools sont fermes sur une Session cote backend (voir
compliance_agent_tools_service.build_compliance_agent_tools, deja generique,
reutilise tel quel -- rechercher_corpus_reglementaire accepte n'importe quel
`domaine` en parametre, aucune modification necessaire pour ce nouveau
sous-domaine).
"""
from typing import Callable

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.shared.groq_runtime.react_agent_runner import ReactAgentError, run_react_agent


class SecnumcloudAgentError(ReactAgentError):
    """Echec d'appel au LLM/agent ou reponse hors schema, meme apres retries."""


class CertificationObligationCandidate(BaseModel):
    nom: str
    description: str
    ordre: int = Field(description="Position de cette etape dans le parcours, en commencant a 1.")
    # source_id REEL d'un chunk vu via rechercher_corpus_reglementaire --
    # meme raisonnement que ObligationCandidate (rgpd_service.py).
    source_id: str | None = Field(
        default=None,
        description="source_id exact d'un chunk vu via l'outil de recherche, ou null si aucun chunk precis ne s'applique.",
    )


class CertificationEstimationCandidate(BaseModel):
    delai_mois_min: int
    delai_mois_max: int
    cout_estime_min: int
    cout_estime_max: int
    justification: str = Field(
        description="Justification citant les sources trouvees, et precisant ce qui est appuye par une source vs un ordre de grandeur indicatif."
    )


class SecnumcloudParcoursResult(BaseModel):
    obligations: list[CertificationObligationCandidate]
    estimation: CertificationEstimationCandidate


def generate_secnumcloud_parcours(tools: list[Callable]) -> SecnumcloudParcoursResult:
    """Parcours SecNumCloud (service 3.3.11) : l'agent recherche dans le

    corpus ANSSI (rechercher_corpus_reglementaire, domaine
    'certification_secnumcloud') et lit le profil du projet (lire_profil_projet)
    avant de produire les etapes ordonnees du parcours et une estimation
    delai/cout. Jamais sans source pour les etapes (meme regle projet que
    RGPD/AI Act/etc) ; l'estimation peut rester un ordre de grandeur explicite
    quand le corpus ne donne aucun chiffre exploitable (voir system prompt).
    """
    config = get_llm_config()["compliance_agent_secnumcloud"]["parcours"]
    system_prompt = get_prompts()["compliance_agent_secnumcloud"]["parcours"]

    try:
        return run_react_agent(
            model=config["model"],
            temperature=config["temperature"],
            system_prompt=system_prompt,
            tools=tools,
            response_format=SecnumcloudParcoursResult,
            task_message="Etablis le parcours vers la qualification SecNumCloud (etapes ordonnees + estimation delai/cout) pour ce projet.",
            # 15, comme les autres sous-agents (rgpd/ai_act/healthtech/fintech).
            # CORRECTIF du 22/09/2026 (v2) -- une premiere version de ce
            # correctif avait baisse cette valeur a 8 pour lutter contre le
            # 413 "Request too large" (Groq, 8000 TPM), mauvais diagnostic :
            # recursion_limit plafonne le nombre d'ETAPES du graphe, pas la
            # taille d'une requete -- 8 coupait l'agent avant qu'il ait fini
            # (2 recherches + 1 lecture de profil + reponse finale depassent
            # deja 8 etapes), d'ou "Recursion limit of 8 reached without
            # hitting a stop condition" au run suivant. Le vrai fix contre le
            # 413 reste _TOP_K_CHUNKS baisse a 5 (compliance_agent_tools_service.py)
            # et le prompt raccourci (moins de tokens par appel) -- aucun des
            # deux ne touche au nombre d'etapes autorisees.
            recursion_limit=15,
        )
    except ReactAgentError as exc:
        raise SecnumcloudAgentError(str(exc)) from exc
