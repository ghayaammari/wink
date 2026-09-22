"""Pages de l'encyclopedie Bpifrance Creation a collecter pour le service
1.1.13, categorie 3 -- pure donnee, memes 2 pages identifiees par recherche
web le 25/09/2026 (voir conversation) : pas de decouverte automatique
(crawling) du site, une liste figee choisie a la main, coherente avec le
principe "jamais deviner silencieusement" deja applique ailleurs dans ce
service.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PageBpifranceEncyclopedie:
    url: str
    titre: str
    sous_theme: str


PAGES_PACTE_FONDATEURS: list[PageBpifranceEncyclopedie] = [
    PageBpifranceEncyclopedie(
        url="https://bpifrance-creation.fr/encyclopedie/structures-juridiques/entreprendre-a-plusieurs/pacte-dassocies-organisation",
        titre="Pacte d'associés : organisation et fonctionnement",
        sous_theme="pacte_associes_generalites",
    ),
    PageBpifranceEncyclopedie(
        url="https://bpifrance-creation.fr/encyclopedie/structures-juridiques/entreprendre-a-plusieurs/bonnes-pratiques-liees-au-pacte",
        titre="Les bonnes pratiques liées au pacte d'associés",
        sous_theme="pacte_associes_bonnes_pratiques",
    ),
]
