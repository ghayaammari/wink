"""Pool de cles API Groq, avec rotation et cooldown sur 429.

Meme raisonnement que le pool de cles Mistral observe dans un autre projet
(rotation round-robin + cooldown 60s par cle apres un 429), adapte a
Groq/LangChain pour Wink. Necessaire des maintenant, pas plus tard :
compliance_agent a deja 5 sous-agents actifs sur la meme cle
(sector_detection, rgpd, ai_act, healthtech_gap, fintech_gap), et
administrative_agent/contract_agent vont ajouter encore plus d'appels Groq
concurrents -- sans pool, un seul sous-agent qui sature le quota
requetes/minute bloque tous les autres, y compris ceux d'un autre agent.

Retro-compatible : avec une seule cle configuree (GROQ_API_KEY seule), le
pool se comporte comme avant (une cle, jamais de rotation) -- ajouter
GROQ_API_KEY_2..5 ou GROQ_API_KEYS active la rotation sans toucher au code
appelant.
"""
from __future__ import annotations

import os
import threading
import time


def get_groq_api_keys() -> list[str]:
    """Cles Groq configurees, dans l'ordre de priorite, dedupliquees.

    GROQ_API_KEY (la cle actuelle, seule requise pour que tout continue de
    fonctionner sans rien changer au .env), GROQ_API_KEY_2 a _5
    (optionnelles, cles supplementaires a ajouter au fur et a mesure), et
    GROQ_API_KEYS (liste separee par des virgules, fusionnee en dernier,
    pratique pour un grand nombre de cles sans multiplier les variables).
    """
    candidates: list[str] = []
    for name in ("GROQ_API_KEY", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5"):
        val = os.environ.get(name, "").strip()
        if val and val not in candidates:
            candidates.append(val)
    for val in os.environ.get("GROQ_API_KEYS", "").split(","):
        val = val.strip()
        if val and val not in candidates:
            candidates.append(val)
    return candidates


class GroqKeyPool:
    """Pool thread-safe de cles Groq, avec cooldown par cle apres un 429.

    `acquire()` renvoie la cle la moins recemment utilisee parmi celles qui
    ne sont pas en cooldown (ou, si toutes le sont, la moins recemment
    utilisee quand meme -- mieux vaut retenter une cle en cooldown que ne
    jamais repondre). `cooldown()` est appele par l'appelant quand Groq
    renvoie un 429 pour la cle utilisee.
    """

    def __init__(self, keys: list[str], cooldown_s: float = 60.0) -> None:
        if not keys:
            raise ValueError("GroqKeyPool necessite au moins une cle.")
        self._keys = keys
        self._cooldown_s = cooldown_s
        self._lock = threading.Lock()
        self._cooldown_until: dict[str, float] = {}
        self._last_used: dict[str, float] = {key: 0.0 for key in keys}

    def acquire(self) -> str:
        now = time.monotonic()
        with self._lock:
            available = [key for key in self._keys if self._cooldown_until.get(key, 0.0) <= now]
            candidates = available or list(self._keys)
            key = min(candidates, key=lambda k: self._last_used[k])
            self._last_used[key] = now
        return key

    def cooldown(self, key: str) -> None:
        with self._lock:
            self._cooldown_until[key] = time.monotonic() + self._cooldown_s

    @property
    def size(self) -> int:
        return len(self._keys)
