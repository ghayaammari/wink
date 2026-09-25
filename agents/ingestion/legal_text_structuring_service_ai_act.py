"""Structuration LLM des articles AI Act collectes (service 3.3.12) — fichier
dedie, meme separation que legal_text_structuring_service_rgpd.py (chaque
pipeline garde son propre service de classification).

Classification PAR LOT (pas par article) — voir docstring de
collect_ai_act_articles.py pour le raisonnement complet : classifier les 119
articles un par un (1 appel filtre + 1 appel classification, comme
l'ancienne version RGPD) aurait fait ~238 appels Groq et tres probablement
repuise le meme quota TPD deja rencontre sur le RGPD. Un seul appel traite
plusieurs articles a la fois — le nombre exact par appel est decide par
l'appelant (voir collect_ai_act_articles.py::_TAILLE_LOT), pas ici.

Meme logique de retry/appel Groq dupliquee que legal_text_structuring_service_rgpd.py,
legal_text_structuring_service.py et sector_insurance_structuring_service.py
— dette technique deja documentee ailleurs (regle de 3 depassee), pas
refactoree ici pour la meme raison (pas en marge d'un ajout de service).
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

# Categories de risque de l'AI Act utilisees pour indexer/filtrer la
# recherche (meme role que SousThemeRGPD, stockees dans la meme colonne
# legal_texts.sous_theme — voir commentaire dans legal_texts.py).
CategorieRisqueAIAct = Literal[
    "interdit",
    "haut_risque",
    "risque_limite",
    "gouvernance_gpai",
    "minimal",
]


class AIActTextStructuringError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


class ArticleClassifieAIAct(BaseModel):
    article_numero: str
    pertinent: bool
    categorie_risque: CategorieRisqueAIAct | None = Field(
        default=None, description="null si pertinent=false"
    )
    chunking_suggere: Literal["aucun", "par_alinea"]
    justification: str = Field(description="Justification courte, une phrase.")


class _BatchClassificationResult(BaseModel):
    articles: list[ArticleClassifieAIAct]


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AIActTextStructuringError("GROQ_API_KEY manquant dans .env.")
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


def _construire_articles_bloc(articles: list[dict]) -> str:
    return "\n\n".join(
        f"### Article {article['article_numero']}\n{article['texte_brut']}" for article in articles
    )


def classify_articles_batch(articles: list[dict]) -> list[ArticleClassifieAIAct]:
    """Filtre + classifie un lot d'articles en UN SEUL appel Groq. `articles` :
    liste de {"article_numero", "texte_brut"} (voir eu_ai_act_client.py).

    Ne garantit PAS qu'une entree soit renvoyee pour chaque article du lot en
    entree (le LLM peut en omettre) — a l'appelant de gerer les numeros
    manquants (voir collect_ai_act_articles.py, qui les ecarte plutot que de
    deviner une classification).
    """
    config = get_llm_config()["ai_act_text_structuration"]["batch_classification"]
    prompt_template = get_prompts()["ai_act_text_structuration"]["batch_classification"]
    prompt = prompt_template.format(
        articles_bloc=_construire_articles_bloc(articles),
        schema_json=json.dumps(_BatchClassificationResult.model_json_schema()),
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
            raise AIActTextStructuringError(f"Échec de l'appel au LLM (Groq, batch_classification) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return _BatchClassificationResult.model_validate_json(raw).articles
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise AIActTextStructuringError(
        f"Le LLM n'a pas produit de JSON valide pour batch_classification après {config['max_retries']} "
        f"tentatives : {last_error}"
    )
