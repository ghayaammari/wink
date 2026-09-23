"""Generation du contenu d'un pitch deck (service 6.6.2) via Groq.

Pas un agent ReAct (pas d'outils, pas de recherche dans un corpus) : toutes
les donnees necessaires (profil pitch + vitrine publique + associes) sont
deja rassemblees par l'appelant (backend/entrepreneur/services/
pitch_deck_service.py) avant l'appel -- une seule tache de generation
structuree, comme grounding_verification_service.py
(agents/shared/groq_runtime/), pas comme les agents de diagnostic
(rgpd_service.py, ai_act_service.py) qui lisent eux-memes le corpus.

`with_structured_output(method="json_schema", strict=True)` (Groq) fait
respecter le schema cote API -- contrairement au prototype startapini
(Mistral, `response_format=json_object` + boucle de reparation manuelle sur
erreur de validation), pas besoin de retry de validation ici : soit l'appel
reussit et le contenu est deja valide, soit il leve une erreur reseau/API
franche.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agents.config.loader import get_llm_config, get_prompts
from agents.pitch_deck_agent.deck_schema import DeckSlides
from langchain_groq import ChatGroq


class PitchDeckAgentError(RuntimeError):
    """Echec d'appel a l'agent (LLM/Groq) -- traduit en 502 par pitch_router.py."""


class TeamMemberInput(BaseModel):
    name: str
    role: str


class PitchGenerationInput(BaseModel):
    """Tout ce que l'agent recoit pour rediger les 11 diapositives -- assemble

    par pitch_deck_service.py a partir de Project/ProjectPublicProfile
    (nom, pitch en une ligne) + ProjectAssociate (equipe) +
    ProjectPitchProfile (le reste, saisi par l'entrepreneur). Champs texte
    libre, potentiellement vides (formulaire pas encore rempli) : c'est au
    prompt de gerer l'absence d'information (voir SYSTEM_PROMPT), pas a ce
    modele de la refuser."""

    startup_name: str
    one_liner: str | None = None
    secteur: str | None = None
    probleme: str | None = None
    solution: str | None = None
    marche: str | None = None
    modele_economique: str | None = None
    concurrence: str | None = None
    traction: str | None = None
    financements: str | None = None
    roadmap: str | None = None
    demande_investissement: str | None = None
    equipe: list[TeamMemberInput] = Field(default_factory=list)


def generer_contenu_deck(donnees: PitchGenerationInput) -> DeckSlides:
    """Un seul appel Groq, sortie garantie conforme a `DeckSlides` par le

    mode json_schema strict. Leve `PitchDeckAgentError` sur tout echec
    (cle API absente, appel Groq en erreur) -- jamais d'exception brute
    remontee jusqu'au router."""
    config = get_llm_config()["pitch_deck_agent"]["generation"]
    system_prompt = get_prompts()["pitch_deck_agent"]["generation"]

    try:
        llm = ChatGroq(model=config["model"], temperature=config["temperature"])
        structured_llm = llm.with_structured_output(DeckSlides, method="json_schema", strict=True)
        return structured_llm.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": donnees.model_dump_json(exclude_none=True)},
            ]
        )
    except Exception as exc:  # noqa: BLE001 -- toute panne Groq devient une erreur agent unique
        raise PitchDeckAgentError(f"Echec de generation du pitch deck : {exc}") from exc
