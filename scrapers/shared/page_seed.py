"""Dataclass partagee decrivant une URL de depart pour la collecte web
(volet non-legal, service 1.1.10). Pure donnee, aucune logique — importee par
les fichiers `pages_assurance.py` de chaque source."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PageSeed:
    url: str
    # Fixe par curation humaine (verification manuelle du contenu de la page
    # avant de l'ajouter ici) — jamais devine par le LLM, meme principe que
    # `secteurs_concernes` dans `blocs_secteurs_assurance.py`.
    secteurs_cibles: list[str] = field(default_factory=list)
    # Crawling borne (profondeur 1, meme domaine uniquement — voir
    # `scrapers/shared/web_fetch.py::discover_links`) depuis cette page.
    max_liens_a_suivre: int = 5
