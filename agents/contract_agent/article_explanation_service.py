"""Explication en langage clair d'un ARTICLE facultatif entier des statuts —
affichée sur l'écran de choix des facultatifs (service 1.1.4, étape 4 de la
refonte du parcours ; relève du service 1.1.15 « Explication des clauses »).

Différences avec `clause_explanation_service.py` (même dossier) :
- granularité ARTICLE (toutes les clauses d'un article facultatif, parfois 2
  articles regroupés, ex. Directeur Général = Art. 23 + 40), pas une clause ;
- aucune valeur saisie : l'explication est la même pour tous les
  utilisateurs (elle aide à DÉCIDER d'inclure l'article, avant toute saisie).
  D'où un usage en BATCH (script `generate_statuts_article_explanations.py`)
  avec stockage + relecture humaine, jamais un appel LLM au clic.
- `document_type` en paramètre dès le départ (réutilisable pour le pacte).

Même séparation IA / base de données que les autres services de ce dossier :
ce module appelle le LLM et renvoie du texte, il ne lit ni n'écrit la base.
"""
import os
import time

from groq import Groq

from agents.config.loader import get_llm_config, get_prompts

_RATE_LIMIT_MAX_ATTEMPTS = 5
_RATE_LIMIT_BASE_DELAY_SECONDS = 3

# Libellé du document dans le prompt, par document_type.
_TYPE_DOCUMENT_LIBELLE = {"statuts": "statuts", "pacte_fondateurs": "pacte de fondateurs"}


class ArticleExplanationError(Exception):
    """Échec d'appel au LLM, même après retries, ou réponse vide."""


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ArticleExplanationError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _create_completion_with_backoff(client: Groq, **kwargs):
    """Même patron que clause_explanation_service._create_completion_with_backoff.
    DETTE ASSUMÉE : 6e copie de ce patron dans agents/ — la factorisation est
    déjà prévue dans un incrément « nettoyage agents/ » dédié (voir les
    docstrings des autres copies), pas faite silencieusement ici."""
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


def explain_article(document_type: str, titre_article: str, texte_article: str) -> str:
    """Explique un article facultatif en 3 à 5 phrases : à quoi il sert, quand
    il est utile, ce qui se passe sans lui. `texte_article` = texte des
    clauses de l'article, concaténées. Renvoie le texte brut."""
    if not texte_article.strip():
        raise ArticleExplanationError(f"Texte vide pour l'article « {titre_article} ».")

    config = get_llm_config()["contract_agent"]["article_explanation"]
    prompt = get_prompts()["contract_agent"]["article_explanation"].format(
        type_document=_TYPE_DOCUMENT_LIBELLE.get(document_type, document_type),
        titre_article=titre_article,
        texte_article=texte_article,
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
            raise ArticleExplanationError(f"Échec de l'appel au LLM (Groq, explication d'article) : {exc}") from exc

        texte = (response.choices[0].message.content or "").strip()
        if texte:
            return texte
        last_error = ValueError("Réponse vide du LLM.")

    raise ArticleExplanationError(
        f"Le LLM n'a pas produit d'explication après {config['max_retries']} tentatives : {last_error}"
    )
