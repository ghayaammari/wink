"""Normalisation de texte pour comparaison insensible à la casse/aux accents —
utilisée par plusieurs clients de scraping pour comparer un nom saisi à un nom
retourné par une API externe (ex: "Nova Robotics" vs "NOVA ROBOTICS"). Même
logique que la comparaison de dénomination de Parcours B (voir page Notion
"Wink — Scénario détaillé : Informations légales, startup déjà créée").
"""
import unicodedata


def fold(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).upper().strip()
