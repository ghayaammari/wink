"""Garde-fou légal sur le texte libre saisi par l'utilisateur pour une clause du
pacte de fondateurs (service 1.1.13, Groupe 5). Décision actée avec
l'utilisateur (20/09/2026) : appel LLM (Groq), pas une approche uniquement
déterministe — les critères structurés de `clause_validity_criteria` (limites
chiffrées, ex. durée max 10 ans) sont fournis en contexte au LLM plutôt que
vérifiés par du code séparé, pour rester cohérent sur un seul chemin de
validation, plus simple à faire évoluer qu'un mélange règles-déterministes +
LLM qui pourraient diverger silencieusement sur le même texte.

Appelée par le router AVANT `document_generation_service.submit_section()`,
uniquement sur les variables de type 'texte' (saisie libre) — jamais sur les
variables typées 'nombre'/'montant'/'date'/'duree'/'nombre_ordinal' (déjà
validées par leur type, aucune formulation à juger), ni sur 'choix' (liste
fermée d'options, validée par correspondance exacte — voir
document_generation_service._validate_variables), ni sur 'reference_croisee'
(résolue par l'application, jamais saisie par l'utilisateur).

Dette technique assumée : logique de retry/appel Groq dupliquée ici plutôt que
factorisée (même choix que legal_text_structuring_service.py). Le seuil de
"3e cas identique" qui justifierait de factoriser (voir sa docstring) est déjà
dépassé avec sector_insurance_structuring_service.py — ce module est donc la
4e occurrence du même patron. Pas traité ici : factoriser proprement suppose
de toucher 3 fichiers déjà en production hors du périmètre du service 1.1.13,
risque disproportionné par rapport à ce module. À faire dans un incrément
dédié "nettoyage agents/ingestion", pas silencieusement au passage ici.
"""
import json
import os
import time

from groq import Groq
from pydantic import BaseModel, Field, ValidationError

from agents.config.loader import get_llm_config, get_prompts

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3


class LegalClauseGuardrailError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


class GuardrailResult(BaseModel):
    autorise: bool
    motif: str = Field(description="Justification courte, une phrase.")
    article_cite: str | None = None
    reformulation_proposee: str | None = None


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LegalClauseGuardrailError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
    """Identique à legal_text_structuring_service._create_completion_with_backoff —
    voir la docstring du module pour la décision de ne pas factoriser."""
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


def _format_criteres(criteres: list[dict]) -> str:
    if not criteres:
        return "(aucun critère structuré connu pour cette section)"
    lignes = []
    for c in criteres:
        limite = f" (limite : {c['valeur_limite']})" if c.get("valeur_limite") else ""
        lignes.append(f"- {c['description_critere']}{limite} — base légale : {c['base_legale']}")
    return "\n".join(lignes)


def check_free_text(texte_libre: str, *, contexte: str, criteres: list[dict] | None = None) -> GuardrailResult:
    """Vérifie un texte libre destiné à une clause du pacte. `criteres` : liste
    de critères issus de `clause_validity_criteria` pour la clause concernée
    (dicts {description_critere, valeur_limite, base_legale}), typiquement lus
    par le router via `clause_validity_criteria_service` avant l'appel — ce
    module reste sans dépendance DB, purement IA (voir séparation agents/ vs
    backend/, DECISIONS.md).
    """
    if not texte_libre or not texte_libre.strip():
        # Rien à vérifier — un champ vide n'est de toute façon pas légalement
        # problématique ; c'est à submit_section() de décider si le champ est requis.
        return GuardrailResult(autorise=True, motif="Texte vide, rien à vérifier.")

    config = get_llm_config()["contract_agent"]["legal_clause_guardrail"]
    prompt_template = get_prompts()["contract_agent"]["legal_clause_guardrail"]
    prompt = prompt_template.format(
        texte_libre=texte_libre,
        contexte=contexte,
        criteres=_format_criteres(criteres or []),
        schema_json=json.dumps(GuardrailResult.model_json_schema()),
    )

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
            raise LegalClauseGuardrailError(f"Échec de l'appel au LLM (Groq, garde-fou pacte) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return GuardrailResult.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise LegalClauseGuardrailError(
        f"Le LLM n'a pas produit de JSON valide pour le garde-fou après {config['max_retries']} tentatives : {last_error}"
    )
