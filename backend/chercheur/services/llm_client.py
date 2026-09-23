"""Client LLM partagé (Groq).

Extrait de paper_llm_service.py : tant qu'un seul fichier appelait le LLM,
garder le client et le parsing JSON dedans était le choix le plus simple.
Avec researcher_profile_llm_service.py comme deuxième vrai consommateur
(résumés de profil, pas juste d'analyse de papiers), la duplication du
client/gestion d'erreur/nettoyage JSON ne se justifiait plus — extrait ici,
les deux fichiers appelants n'ont plus à connaître Groq/OpenAI directement.

Modèle et température lus depuis agents/config/llm_config.yaml
(chercheur_llm.analysis), plus jamais en dur ici — corrigé le 22/09/2026 :
le modèle était codé en dur (qwen/qwen3.6-27b), retiré depuis du catalogue
Groq (404 model_not_found constaté en extraction réelle), sans que
llm_config.yaml — pourtant "un seul endroit à modifier pour changer de
modèle" selon son propre docstring — ne soit consulté. Voir ce fichier pour
le choix de remplacement (openai/gpt-oss-120b, déjà utilisé partout ailleurs
dans le projet)."""
import json
import logging
import os

from openai import OpenAI

from agents.config.loader import get_llm_config

_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

logger = logging.getLogger(__name__)


class LLMExtractionError(Exception):
    """Levée si l'appel API échoue (réseau, quota, timeout) ou si la réponse
    n'est pas un JSON exploitable. Le seul type d'erreur que ce module lève
    vers l'appelant — les services métier n'ont pas à connaître le détail du
    fournisseur LLM derrière."""


def call_and_parse(prompt: str, max_tokens: int) -> dict:
    config = get_llm_config()["chercheur_llm"]["analysis"]
    text = None
    try:
        response = _client.chat.completions.create(
            model=config["model"],
            max_tokens=max_tokens,
            temperature=config["temperature"],
            # "low" et non "none" (valeur qwen3 uniquement, incompatible avec
            # gpt-oss) : les modèles openai/gpt-oss-* de Groq supportent
            # low/medium/high — "low" laisse un minimum de raisonnement tout
            # en réservant l'essentiel de max_tokens à la réponse JSON, même
            # intention que "none" avec Qwen (voir git blame).
            reasoning_effort="low",
            response_format={"type": "json_object"},  # force un JSON syntaxiquement
                                                        # valide côté API plutôt que de
                                                        # compter uniquement sur la
                                                        # consigne du prompt
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content
        return json.loads(_strip_json_fences(text))
    except Exception as exc:
        # Log de la réponse brute pour diagnostiquer un futur échec de
        # parsing sans avoir à le reproduire à l'aveugle. Le message de exc
        # (rate limit, clé invalide, timeout...) est propagé tel quel dans
        # LLMExtractionError — c'est lui qui doit apparaître dans les logs
        # appelants, pas un message générique qui masquerait la vraie cause.
        logger.debug("Réponse LLM brute non parsable : %s", text if text is not None else "<pas de réponse reçue>")
        raise LLMExtractionError(f"Appel LLM échoué ou réponse invalide : {exc}") from exc


def _strip_json_fences(text: str) -> str:
    """Deux nettoyages nécessaires avec les réponses de modèles Groq :
    1. Un mode 'thinking' peut préfixer la réponse d'un raisonnement entre
       balises <think>...</think> — à retirer avant de parser.
    2. Comme la plupart des modèles, il enrobe parfois le JSON de ```json```
       malgré la consigne de ne pas le faire."""
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[1].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1].removeprefix("json").strip()
    return cleaned
