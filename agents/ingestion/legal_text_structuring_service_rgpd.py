"""Structuration LLM des textes RGPD collectes (service 3.3.1) — fichier
dedie, ne modifie pas legal_text_structuring_service.py (meme principe
SOLID/SRP que sector_insurance_structuring_service.py : chaque pipeline a
son propre service de classification, pas un seul fichier avec un SousTheme
generique partage entre domaines sans rapport).

Sources traitees par ce service : articles de la Loi n°78-17 (Legifrance,
via texte_loi_rgpd.py) ET guides/FAQ/PDF CNIL (via pages_rgpd.py) — les deux
passent par le meme filtre de pertinence + classification, meme si leur
texte source a une forme differente (article de loi structure vs page web
editoriale) : le besoin de filtrage/classification est identique.

Meme logique de retry/appel Groq dupliquee que legal_text_structuring_service.py
et sector_insurance_structuring_service.py — dette technique mineure assumee,
a factoriser (regle de 3, maintenant atteinte avec ce 3e fichier) si un 4e
cas de structuration LLM apparait. Pas fait ici : appliquer la regle de 3
retroactivement sur 3 fichiers deja ecrits et testes serait un refactor a
part entiere, pas un ajout — a faire dans une passe dediee, pas en marge de
la collecte RGPD.
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

SousThemeRGPD = Literal[
    "registre_traitements",
    "aipd",
    "dpo",
    "bases_legales",
    "droits_personnes",
    "securite_donnees",
    "transferts_hors_ue",
]


class RGPDTextStructuringError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


class RelevanceResult(BaseModel):
    pertinent: bool
    justification: str = Field(description="Justification courte, une phrase.")


class ClassificationResult(BaseModel):
    sous_theme: SousThemeRGPD
    chunking_suggere: Literal["aucun", "par_alinea"]


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RGPDTextStructuringError("GROQ_API_KEY manquant dans .env.")
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
    config = get_llm_config()["rgpd_text_structuration"][prompt_key]
    prompt_template = get_prompts()["rgpd_text_structuration"][prompt_key]
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
            raise RGPDTextStructuringError(f"Échec de l'appel au LLM (Groq, {prompt_key}) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise RGPDTextStructuringError(
        f"Le LLM n'a pas produit de JSON valide pour {prompt_key} après {config['max_retries']} tentatives : {last_error}"
    )


def filter_article_relevance(texte_brut: str) -> RelevanceResult:
    return _call_llm("relevance_filter", texte_brut, RelevanceResult)


def classify_article(texte_brut: str) -> ClassificationResult:
    return _call_llm("classification", texte_brut, ClassificationResult)
