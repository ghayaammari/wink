"""Structuration LLM des textes collectes pour les assurances sectorielles
(service 1.1.10) — fichier dedie, ne modifie pas
`legal_text_structuring_service.py` (principe SOLID/SRP : chaque pipeline a
son propre service de classification).

Un seul appel LLM par texte source : produit `type_assurance` +
`a_base_legale` + `chunking_suggere`. `a_base_legale` n'est jamais presume
par defaut (le schema Notion le precise : "sans presumer arbitrairement") :
le LLM ne repond `true` que s'il identifie une reference legale explicite
dans le texte.

Meme logique de retry/appel Groq que `legal_text_structuring_service.py`
(dette technique mineure assumee — a factoriser si un 4e cas apparait,
voir "regle de 3" dans la docstring de l'autre fichier).

CORRECTIF du 12/09/2026 — 413 Groq recurrents ("tokens per minute (TPM):
Limit 8000") meme apres avoir tronque le texte envoye a la classification
(voir `_TEXTE_CLASSIFICATION_LONGUEUR_MAX` dans
`collect_sector_insurance_pages.py`) : la preuve que ce n'etait pas un
probleme de taille d'UNE requete, c'est que le nombre de tokens "Requested"
dans l'erreur variait a peine (10568 puis 10535) alors que le texte envoye
avait ete divise par plus de 3. Le tier "on_demand" applique un plafond
CUMULE sur une fenetre de 60s, pas seulement par requete — et ce pipeline
enchaine plusieurs appels Groq (filtre + classification, par page x par
secteur) sans aucune pause. Deux defenses ajoutees, complementaires :
  1. `_respect_groq_rate_limit()` — espace chaque appel Groq d'au moins
     `_GROQ_MIN_DELAY_SECONDS`, meme principe que `_respect_rate_limit()`
     dans `scrapers/shared/web_fetch.py` mais applique au budget Groq
     (partage par tous les appels de ce module) plutot qu'a un domaine web.
     Reduit le risque de depasser le plafond AVANT qu'il ne se produise.
  2. `_create_completion_with_backoff()` retente desormais aussi sur un 413
     dont le corps contient `rate_limit_exceeded` (pas seulement 429) —
     filet de securite si la pause n'a pas suffi (ex: plusieurs processus
     concurrents sur la meme cle).
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

# Delai minimum entre deux appels Groq, tous types confondus (filtre,
# chunking, classification) — voir le correctif du 12/09/2026 dans la
# docstring du module. 8s est une valeur prudente, choisie pour rester
# largement sous 8000 TPM meme dans le pire cas (~3000 caracteres, le
# plafond de `_TEXTE_CLASSIFICATION_LONGUEUR_MAX`), pas calculee au token
# pres : dette technique assumee, a resserrer si la collecte devient trop
# lente en pratique.
_GROQ_MIN_DELAY_SECONDS = 8.0
_last_groq_call_at: float | None = None


class SectorInsuranceStructuringError(Exception):
    """Echec d'appel au LLM ou reponse hors schema, meme apres retries."""


class ClassificationResult(BaseModel):
    type_assurance: str = Field(description="Ex: RC Pro, Assurance decennale, Cyber, Flotte...")
    a_base_legale: bool = Field(description="true uniquement si une reference legale explicite est citee dans le texte.")
    chunking_suggere: Literal["aucun", "par_alinea"] = Field(
        description="aucun si sujet unique, par_alinea si sujets distincts par alinea."
    )


class PageRelevanceResult(BaseModel):
    pertinent: bool
    justification: str = Field(description="Justification courte, une phrase.")


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise SectorInsuranceStructuringError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def _respect_groq_rate_limit() -> None:
    """Espace les appels Groq d'au moins `_GROQ_MIN_DELAY_SECONDS` — evite de
    bruler le budget TPM cumule avant meme qu'un 413/429 ne se produise.
    Log explicite quand une pause a vraiment lieu, pour que l'attente soit
    visible dans la sortie du script plutot que de laisser le pipeline
    silencieux pendant plusieurs secondes."""
    global _last_groq_call_at
    if _last_groq_call_at is not None:
        elapsed = time.time() - _last_groq_call_at
        restant = _GROQ_MIN_DELAY_SECONDS - elapsed
        if restant > 0:
            print(f"      (pause {restant:.1f}s — limite Groq tokens/minute)")
            time.sleep(restant)
    _last_groq_call_at = time.time()


def _create_completion_with_backoff(client: Groq, **kwargs):
    delay = _RATE_LIMIT_BASE_DELAY_SECONDS
    for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
        _respect_groq_rate_limit()
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            # Groq renvoie parfois un 413 (pas 429) pour un depassement de
            # quota TPM cumule plutot qu'une requete individuellement trop
            # grosse (voir docstring du module) — traite comme un rate limit
            # retryable dans les deux cas.
            is_rate_limit = status_code == 429 or (
                status_code == 413 and "rate_limit_exceeded" in str(exc)
            )
            if not is_rate_limit or attempt == _RATE_LIMIT_MAX_ATTEMPTS - 1:
                raise
            print(f"      [RETRY] Groq rate limit (tentative {attempt + 1}/{_RATE_LIMIT_MAX_ATTEMPTS}) — pause {delay}s.")
            time.sleep(delay)
            delay += _RATE_LIMIT_BASE_DELAY_SECONDS


def filter_page_relevance(secteur: str, titre: str, extrait: str) -> PageRelevanceResult:
    """Filtre bon marche avant `classify_insurance_text()`, appele sur le
    titre + un court extrait d'une page reellement recuperee par
    `scrapers/shared/web_fetch.py::fetch_page()` (jamais sur une URL seule
    ni un snippet de moteur de recherche externe). Meme schema deux-etapes
    que `filter_article_relevance()` dans `legal_text_structuring_service.py`.
    """
    config = get_llm_config()["sector_insurance_structuration"]["page_relevance"]
    prompt_template = get_prompts()["sector_insurance_structuration"]["page_relevance"]
    prompt = prompt_template.format(
        secteur=secteur,
        titre=titre,
        extrait=extrait,
        schema_json=json.dumps(PageRelevanceResult.model_json_schema()),
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
            raise SectorInsuranceStructuringError(
                f"Echec de l'appel au LLM (Groq, sector_insurance page_relevance) : {exc}"
            ) from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return PageRelevanceResult.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise SectorInsuranceStructuringError(
        f"Le LLM n'a pas produit de JSON valide apres {config['max_retries']} tentatives : {last_error}"
    )


class ChunkingResult(BaseModel):
    chunking_suggere: Literal["aucun", "par_alinea"] = Field(
        description="aucun si sujet unique, par_alinea si sujets distincts par alinea."
    )


def detect_chunking(texte_brut: str) -> ChunkingResult:
    """Determine chunking_suggere a partir du seul texte brut — pas de
    `secteur` en entree, contrairement a `classify_insurance_text()`. Fonction
    partagee par les 2 volets du service 1.1.10 :
    - volet 1 (Legifrance) : le secteur est deja connu par bloc, mais
      chunking_suggere ne depend pas du secteur, seulement de la structure du
      texte de l'article — pas besoin de le repasser en parametre.
    - volet 2 (pages web) : le secteur de la page n'est pas encore determine
      a ce stade du pipeline, cette fonction doit donc pouvoir tourner sans.
    """
    config = get_llm_config()["sector_insurance_structuration"]["chunking"]
    prompt_template = get_prompts()["sector_insurance_structuration"]["chunking"]
    prompt = prompt_template.format(
        texte_brut=texte_brut,
        schema_json=json.dumps(ChunkingResult.model_json_schema()),
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
            raise SectorInsuranceStructuringError(
                f"Echec de l'appel au LLM (Groq, sector_insurance chunking) : {exc}"
            ) from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return ChunkingResult.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise SectorInsuranceStructuringError(
        f"Le LLM n'a pas produit de JSON valide apres {config['max_retries']} tentatives : {last_error}"
    )


def classify_insurance_text(texte_brut: str, secteur: str) -> ClassificationResult:
    """Classifie un texte source en un type d'assurance pour un secteur donne."""
    config = get_llm_config()["sector_insurance_structuration"]["classification"]
    prompt_template = get_prompts()["sector_insurance_structuration"]["classification"]
    prompt = prompt_template.format(
        texte_brut=texte_brut,
        secteur=secteur,
        schema_json=json.dumps(ClassificationResult.model_json_schema()),
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
            raise SectorInsuranceStructuringError(
                f"Echec de l'appel au LLM (Groq, sector_insurance classification) : {exc}"
            ) from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return ClassificationResult.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise SectorInsuranceStructuringError(
        f"Le LLM n'a pas produit de JSON valide apres {config['max_retries']} tentatives : {last_error}"
    )
