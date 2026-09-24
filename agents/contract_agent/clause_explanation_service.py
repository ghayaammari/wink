"""Explication en langage clair d'une clause du pacte de fondateurs — service
1.1.15 (Explication des clauses d'un document généré par la plateforme),
contextualisée aux valeurs déjà saisies par l'utilisateur pour cette clause.

Décision actée avec l'utilisateur (22/09/2026) : appel LLM (Groq) sur le
texte FIGÉ de la clause (déjà assemblée par le moteur de clauses-template,
voir document_generation_service.py) — ce service explique la clause, il ne
la rédige jamais. Même séparation agents/ (IA) vs backend/.../services (DB)
que legal_clause_guardrail_service.py : appelé par le router APRÈS résolution
de la clause (resolve_target_clause, lecture pure côté service DB), jamais
l'inverse.

DIFFÉRENT du tool `expliquer_clause` du copilot
(agents/agent_pacte_fondateur/tools/expliquer_clause_tool.py) : celui-ci fait
de la recherche sémantique (RAG) sur le corpus juridique et répond à une
question libre en conversation, persistée dans l'historique du copilot.
Celui-là (ce module) est un appel LLM unique qui prend le texte de la clause
+ les valeurs RÉELLEMENT saisies par l'utilisateur (potentiellement
partielles, avant même validation de la section — l'utilisateur peut
survoler un titre avant d'avoir fini de remplir le formulaire) et explique ce
que ces valeurs signifient concrètement — personnalisé, jamais générique tant
que des valeurs existent. Les deux coexistent volontairement (voir échange du
22/09/2026) : le hover sur un titre de clause (ClauseTitleExplainV2.tsx)
appelle CE service, pas le tool du copilot.
"""
import os
import time

from groq import Groq

from agents.config.loader import get_llm_config, get_prompts

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3


class ClauseExplanationError(Exception):
    """Échec d'appel au LLM, même après retries, ou réponse vide."""


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ClauseExplanationError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
    """Identique à legal_clause_guardrail_service._create_completion_with_backoff
    — même décision de ne pas factoriser (voir sa docstring : déjà la 4e
    occurrence du patron dans le repo, celle-ci la 5e — à traiter dans un
    incrément "nettoyage agents/" dédié, pas silencieusement ici)."""
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


def _format_valeurs(variables_requises: list[dict], valeurs: dict) -> str:
    """Traduit {nom_variable: valeur} en lignes lisibles par le LLM, avec le
    libellé humain plutôt que le nom technique. Valeurs vides/absentes
    ignorées (un champ pas encore rempli n'apporte rien à l'explication)."""
    if not valeurs:
        return "(aucune valeur saisie pour l'instant — explique la clause de manière générale, sans supposer de choix précis)"

    libelles = {v["nom"]: v.get("libelle", v["nom"]) for v in variables_requises}
    lignes = [f"- {libelles.get(nom, nom)} : {valeur}" for nom, valeur in valeurs.items() if valeur]
    if not lignes:
        return "(aucune valeur saisie pour l'instant — explique la clause de manière générale, sans supposer de choix précis)"
    return "\n".join(lignes)


def explain_clause(texte_clause: str, variables_requises: list[dict], valeurs: dict | None = None) -> str:
    """Explique `texte_clause` en langage clair, contextualisé aux `valeurs`
    déjà saisies (peut être vide ou partiel). Retourne le texte brut de
    l'explication (pas de schéma JSON à parser ici — contrairement au
    garde-fou, il n'y a rien à valider structurellement, juste du texte)."""
    config = get_llm_config()["contract_agent"]["clause_explanation"]
    prompt_template = get_prompts()["contract_agent"]["clause_explanation"]
    prompt = prompt_template.format(
        texte_clause=texte_clause,
        valeurs_saisies=_format_valeurs(variables_requises, valeurs or {}),
    )

    client = _get_client()
    last_error: Exception | None = None
    for _ in range(config["max_retries"]):
        try:
            response = _create_completion_with_backoff(
                client,
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=config["temperature"],
            )
        except Exception as exc:
            raise ClauseExplanationError(f"Échec de l'appel au LLM (Groq, explication de clause) : {exc}") from exc

        texte = (response.choices[0].message.content or "").strip()
        if texte:
            return texte
        last_error = ValueError("Réponse vide du LLM.")

    raise ClauseExplanationError(
        f"Le LLM n'a pas produit d'explication après {config['max_retries']} tentatives : {last_error}"
    )
