"""Dataclass partagée décrivant une page de guide pratique à collecter telle
quelle (sans crawling). Pure donnée. Distincte de `PageSeed` (volet
assurance, 1.1.10), dont les champs (`secteurs_cibles`, crawling) n'ont pas
de sens ici.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GuidePage:
    url: str
    # Sujet principal, fixé par curation humaine (contenu de la page vérifié
    # avant ajout) — jamais deviné par un LLM.
    sous_theme: str
