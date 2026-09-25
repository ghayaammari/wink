"""Structuration LLM des textes SecNumCloud collectes (service 3.3.11) —

fichier dedie, meme principe SOLID/SRP que legal_text_structuring_service_rgpd.py
(chaque pipeline a son propre service de classification, pas un SousTheme
generique partage entre domaines sans rapport). Regle de 3 deja identifiee et
deliberement non factorisee (voir docstring de legal_text_structuring_service_rgpd.py) :
ce 4e fichier quasi identique confirme le besoin mais le refactor reste hors
perimetre de cette collecte, comme deja acte.

Sources traitees : referentiel d'exigences SecNumCloud (PDF ANSSI) et FAQ/
guides de qualification (HTML/PDF ANSSI) — voir scrapers/anssi/pages_secnumcloud.py.

4 sous-themes, deduits du contenu reel des pages curees (referentiel +
FAQ qualification) : le referentiel couvre des exigences techniques ET des
exigences de gouvernance/organisation (chapitres distincts du document), la
FAQ couvre le processus de qualification et separement la duree/le cout —
donc 4 categories utiles pour le futur agent, pas une taxonomie inventee a
priori.
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

SousThemeSecnumcloud = Literal[
    "exigences_techniques_securite",
    "exigences_gouvernance_organisation",
    "processus_qualification",
    "delai_cout_duree_validite",
]


class SecnumcloudTextStructuringError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


class RelevanceResult(BaseModel):
    pertinent: bool
    justification: str = Field(description="Justification courte, une phrase.")


class ClassificationResult(BaseModel):
    sous_theme: SousThemeSecnumcloud
    chunking_suggere: Literal["aucun", "par_alinea"]


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise SecnumcloudTextStructuringError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
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
    config = get_llm_config()["secnumcloud_text_structuration"][prompt_key]
    prompt_template = get_prompts()["secnumcloud_text_structuration"][prompt_key]
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
            raise SecnumcloudTextStructuringError(f"Échec de l'appel au LLM (Groq, {prompt_key}) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise SecnumcloudTextStructuringError(
        f"Le LLM n'a pas produit de JSON valide pour {prompt_key} après {config['max_retries']} tentatives : {last_error}"
    )


def filter_article_relevance(texte_brut: str) -> RelevanceResult:
    return _call_llm("relevance_filter", texte_brut, RelevanceResult)


def classify_article(texte_brut: str) -> ClassificationResult:
    return _call_llm("classification", texte_brut, ClassificationResult)
