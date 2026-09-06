"""Extraction structurée : texte brut → champs typés, validés par un schéma
Pydantic, via gpt-oss-120b (Groq). Un appel = un schéma = une table cible (voir
`pipelines/default_pipeline.py`, qui fait 3 appels séparés pour projects,
project_legal_profiles, project_public_profiles).

Sortie forcée en JSON (response_format=json_object) puis validée par le schéma
Pydantic appelant — si le JSON ne respecte pas le schéma, on retente plutôt que
de propager une donnée corrompue vers project_field_values.
"""

import json
import os

from groq import Groq
from pydantic import BaseModel, ValidationError

from agents.config.loader import get_llm_config, get_prompts


class LlmExtractionError(Exception):
    """Échec d'appel au LLM ou réponse qui ne respecte pas le schéma attendu, même après retries."""


def _get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise LlmExtractionError("GROQ_API_KEY manquant dans .env.")
    return Groq(api_key=api_key)


def extract_structured(text: str, schema: type[BaseModel], *, schema_key: str | None = None) -> BaseModel:
    """Extrait les champs de `schema` depuis `text`.

    Tous les champs de `schema` doivent être optionnels (défaut None) : un
    document ne mentionne jamais tous les champs, et un champ non trouvé doit
    rester None plutôt que de forcer le LLM à halluciner une valeur pour
    satisfaire un champ requis.

    `schema_key` identifie la table cible (ex: "projects") pour aller chercher
    ses instructions spécifiques dans prompts.yaml → schema_hints — un prompt
    générique unique ne peut pas porter de règles propres à un domaine (ex:
    format SIREN/SIRET pour le légal, distinction sector/subsectors pour
    projects). `None` ou une clé absente de schema_hints : pas de bloc
    supplémentaire, comportement identique à avant cet ajout.
    """
    config = get_llm_config()["document_processing"]["llm_structuration"]
    client = _get_client()
    schema_json = schema.model_json_schema()
    prompts = get_prompts()["document_processing"]["llm_structuration"]
    prompt_template = prompts["extraction"]
    schema_hints = prompts.get("schema_hints", {}).get(schema_key, "") if schema_key else ""
    prompt = prompt_template.format(schema_json=json.dumps(schema_json), text=text, schema_hints=schema_hints)

    last_error: Exception | None = None
    for _ in range(config["max_retries"]):
        try:
            response = client.chat.completions.create(
                model=config["model"],
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=config["temperature"],
            )
        except Exception as exc:
            # Erreur réseau/API — pas la peine de retenter, ce n'est pas un problème de
            # format de réponse.
            raise LlmExtractionError(f"Échec de l'appel au LLM (Groq) : {exc}") from exc

        raw = response.choices[0].message.content or "{}"
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = exc
            continue

    raise LlmExtractionError(
        f"Le LLM n'a pas produit de JSON valide pour le schéma {schema.__name__} "
        f"après {config['max_retries']} tentatives : {last_error}"
    )
