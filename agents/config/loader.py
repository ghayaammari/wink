"""Charge `agents/config/llm_config.yaml` et `agents/config/prompts.yaml` une
seule fois chacun (cache module-level), partagés par tous les agents/services qui
en ont besoin.

Ajouté en plus de l'arborescence proposée dans le doc de décision : sans lui,
chaque service qui lit un yaml devrait dupliquer sa propre logique de lecture de
fichier — un seul point de lecture par fichier, cohérent avec le rôle de
`agents/config/` ("centraliser les réglages de tous les agents en un seul
endroit").
"""

from pathlib import Path

import yaml

_LLM_CONFIG_PATH = Path(__file__).parent / "llm_config.yaml"
_PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"

_llm_config: dict | None = None
_prompts: dict | None = None


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_llm_config() -> dict:
    global _llm_config
    if _llm_config is None:
        _llm_config = _load_yaml(_LLM_CONFIG_PATH)
    return _llm_config


def get_prompts() -> dict:
    global _prompts
    if _prompts is None:
        _prompts = _load_yaml(_PROMPTS_PATH)
    return _prompts
