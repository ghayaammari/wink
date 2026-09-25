"""Verification d'ancrage (grounding) de la reponse du copilot par rapport

aux chunks reellement recuperes via rechercher_corpus_reglementaire --
repond au besoin "comment verifier que le LLM repond d'apres les chunks et
non par lui-meme" (conversation produit du 20/09/2026). Un second appel
Groq, independant du premier (agents/orchestrator/copilot_agent_service.py),
qui ne voit QUE la reponse et les chunks -- jamais la question d'origine ni
le raisonnement de l'agent -- pour juger si le contenu factuel de la
reponse est soutenu par ces chunks precis.

Volontairement simple (V1) : un verdict global (ancre: bool) + la liste des
affirmations non etayees si besoin, pas de decoupage phrase par phrase avec
score de confiance, et pas de boucle de re-generation automatique si le
verdict est negatif -- la reponse est renvoyee telle quelle, seulement
annotee (voir copilot_agent_service.py::verifier_reponse). Une
auto-correction (redemander une reponse au premier agent en cas d'echec de
verification) serait une vraie fonctionnalite a part, pas construite ici
(voir "reste sobre", instructions du projet).

Cout/latence assumes : un appel Groq supplementaire a chaque message du
copilot qui a declenche au moins un rechercher_corpus_reglementaire (jamais
sur une reponse generale sans recherche, voir verifier_reponse) -- prix
accepte de la garantie anti-hallucination sur un copilot dont le produit
interdit explicitement d'inventer une obligation ou un chiffre (voir
Wink_context_project.md, section "Architecture technique envisagee").

Portee actuelle : uniquement le copilot conversationnel. Les 5 sous-agents
de diagnostic (RGPD, AI Act, HealthTech, FinTech, detection secteur) ont
deja leur propre garde-fou de sortie (validation de `source_id` contre
`seen_source_ids`, voir Wink_compliance_agent_recap.md section 4) --
brancher aussi cette verification d'ancrage dessus serait possible mais pas
demande, a construire separement si besoin.
"""
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq

from agents.config.loader import get_llm_config, get_prompts


class VerificationAncrage(BaseModel):
    ancre: bool = Field(
        description="True si tout le contenu factuel de la reponse est soutenu par au moins un chunk fourni."
    )
    affirmations_non_etayees: list[str] = Field(
        default_factory=list,
        description="Affirmations factuelles de la reponse non soutenues par les chunks fournis. Vide si ancre=True.",
    )


def verifier_ancrage(reponse: str, chunks: list[dict]) -> VerificationAncrage:
    """Appelle un LLM independant pour juger si `reponse` est soutenue par

    `chunks` (liste de {source_id, texte} reellement recuperes pendant le
    tour de conversation, voir seen_chunks dans
    compliance_agent_tools_service.py). N'a jamais acces a la question
    d'origine ni au raisonnement de l'agent : seul le contenu factuel de la
    reponse compte ici, pas sa pertinence ou son utilite.

    method="json_schema" (pas "function_calling") : tache de classification
    simple, un seul appel, pas de ReAct/tools -- inutile de passer par
    react_agent_runner.py, reserve aux agents a raisonnement multi-etapes.
    """
    config = get_llm_config()["copilot_orchestrator"]["grounding_verification"]
    system_prompt = get_prompts()["copilot_orchestrator"]["grounding_verification"]

    llm = ChatGroq(model=config["model"], temperature=config["temperature"])
    structured_llm = llm.with_structured_output(VerificationAncrage, method="json_schema", strict=True)

    chunks_texte = "\n\n".join(f"[{chunk['source_id']}] {chunk['texte']}" for chunk in chunks)
    contenu = f"Reponse a verifier :\n{reponse}\n\nChunks disponibles (seule source autorisee) :\n{chunks_texte}"

    return structured_llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": contenu},
        ]
    )
