"""Dataclass partagee decrivant une URL de depart pour la collecte de
`administrative_guides` (volet non-legal, domaines pacte_fondateurs/pre_depot).
Distincte de `page_seed.PageSeed` (volet assurance) : pas de `secteurs_cibles`
ici, le domaine est fixe par le fichier `pages_*.py` qui importe cette
dataclass, jamais devine par un LLM — voir administrative_guides.py."""
from dataclasses import dataclass


@dataclass(frozen=True)
class AdministrativeGuideSeed:
    url: str
    # Crawling borne (profondeur 1, meme domaine uniquement — voir
    # `scrapers/shared/web_fetch.py::discover_links`) depuis cette page.
    # 0 par defaut : chaque URL est deja curee a la main, pas besoin de
    # decouvrir des pages voisines sauf indication contraire.
    max_liens_a_suivre: int = 0
