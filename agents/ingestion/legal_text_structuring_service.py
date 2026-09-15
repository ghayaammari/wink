"""Structuration LLM des articles Légifrance collectés (service 1.1.1, Groupe 2)
— 2 appels distincts par article, jamais sur le texte lui-même (texte_brut n'est
ni modifié ni halluciné ici, seulement lu).

filter_article_relevance() : filtre de pertinence (Étape 1.3 du plan) — écarte
les articles hors-sujet avant classification.

classify_article() : produit sous_theme + chunking_suggere en UN SEUL appel
(Étape 1.4). NE produit PLUS forme_juridique_concernee (Notion, page (4),
"Corrigé") : ce champ est maintenant fixé par bloc dans
blocs_formes_juridiques.py, jamais deviné par le LLM article par article —
chaque bloc collecté correspond déjà à une ou plusieurs formes connues
d'avance, comme code_source. Voir l'orchestrateur, qui lit
bloc.forme_juridique_concernee au lieu du résultat de cet appel.

Logique de retry/appel Groq dupliquée ici plutôt que réutilisée depuis
`agents/shared/document_processing/llm_extraction/llm_service.py::extract_structured`
— dette technique mineure assumée : ce dernier lit sa config depuis un chemin
YAML fixe (document_processing.llm_structuration), pas généralisable sans le
modifier. À factoriser si un 3e cas de structuration LLM apparaît (règle de 3),
pas avant.

Retry séparé pour les limites de débit Groq (429) : vu en pratique lors de la
collecte réelle — le compte gratuit a un plafond bas de tokens/minute (8000),
largement atteignable sur un bloc de plusieurs dizaines d'articles (2 appels
par article). C'est un retry différent de celui géré par `_call_llm`
ci-dessous (JSON invalide) : ici l'appel échoue avant même d'obtenir une
réponse, pas la peine de le compter dans max_retries.
"""
import json
import os
import time
from typing import Literal

from groq import Groq
from pydantic import BaseModel, Field, ValidationError

from agents.config.loader import get_llm_config, get_prompts

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3

SousTheme = Literal["regime_social", "gouvernance", "fiscalite", "responsabilite", "capital_social"]


class LegalTextStructuringError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


class RelevanceResult(BaseModel):
    pertinent: bool
    justification: str = Field(description="Justification courte, une phrase.")


class ClassificationResult(BaseModel):
    sous_theme: SousTheme
    chunking_suggere: Literal["aucun", "par_alinea"]


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LegalTextStructuringError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
    """Comme client.chat.completions.create(), mais retente automatiquement en
    cas de 429 (limite de débit Groq) avec un délai croissant — voir docstring
    du module. Relance toute autre erreur immédiatement, sans attendre.
    """
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


def _call_llm(prompt_key: str, texte_brut: str, schema: type[BaseModel]) -> BaseModel:
    config = get_llm_config()["legal_text_structuration"][prompt_key]
    prompt_template = get_prompts()["legal_text_structuration"][prompt_key]
    prompt = prompt_template.format(texte_brut=texte_brut, schema_json=json.dumps(schema.model_json_schema()))

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
            raise LegalTextStructuringError(f"Échec de l'appel au LLM (Groq, {prompt_key}) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise LegalTextStructuringError(
        f"Le LLM n'a pas produit de JSON valide pour {prompt_key} après {config['max_retries']} tentatives : {last_error}"
    )


def filter_article_relevance(texte_brut: str) -> RelevanceResult:
    return _call_llm("relevance_filter", texte_brut, RelevanceResult)


def classify_article(texte_brut: str) -> ClassificationResult:
    return _call_llm("classification", texte_brut, ClassificationResult)
