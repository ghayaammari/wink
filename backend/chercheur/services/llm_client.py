"""Client LLM partagé (Qwen via Groq).

Extrait de paper_llm_service.py : tant qu'un seul fichier appelait le LLM,
garder le client et le parsing JSON dedans était le choix le plus simple.
Avec researcher_profile_llm_service.py comme deuxième vrai consommateur
(résumés de profil, pas juste d'analyse de papiers), la duplication du
client/gestion d'erreur/nettoyage JSON ne se justifiait plus — extrait ici,
les deux fichiers appelants n'ont plus à connaître Groq/OpenAI directement.
"""
import json
import logging
import os

from openai import OpenAI

MODEL = "qwen/qwen3.6-27b"

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
    text = None
    try:
        response = _client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            reasoning_effort="none",  # coupe le thinking Qwen — sinon il consomme
                                       # tout max_tokens en raisonnement interne,
                                       # ne laissant rien pour la réponse JSON
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
    """Deux nettoyages nécessaires avec Qwen :
    1. Le mode 'thinking' peut préfixer la réponse d'un raisonnement entre
       balises <think>...</think> — à retirer avant de parser.
    2. Comme la plupart des modèles, il enrobe parfois le JSON de ```json```
       malgré la consigne de ne pas le faire."""
    cleaned = text.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>", 1)[1].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1].removeprefix("json").strip()
    return cleaned
