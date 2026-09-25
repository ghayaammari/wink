"""URLs de depart Bpifrance Creation pour la collecte web du domaine
`pacte_fondateurs` (agent reglementaire, Increment 1). Pure donnee — le
contenu reel est recupere a l'execution par
`scrapers/shared/web_fetch.py::fetch_page()`, jamais ecrit ici.

Verifie manuellement le 24/09/2026 (WebFetch reel, pas suppose) : les 4 pages
existent, repondent 200, contenu extrait coherent (guide reel sur le pacte
d'associes/d'actionnaires, pas une page de redirection ou de recherche)."""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed

NOM_SOURCE = "Bpifrance Creation"
DOMAINE = "pacte_fondateurs"

PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(
        url="https://bpifrance-creation.fr/encyclopedie/structures-juridiques/entreprendre-a-plusieurs/pacte-dassocies-organisation",
    ),
    AdministrativeGuideSeed(
        url="https://bpifrance-creation.fr/pacte-dactionnaires",
    ),
    AdministrativeGuideSeed(
        url="https://bpifrance-creation.fr/boiteaoutils/modele-gratuit-pacte-dassocies-sas",
    ),
    AdministrativeGuideSeed(
        url="https://bpifrance-creation.fr/encyclopedie/structures-juridiques/entreprendre-a-plusieurs/bonnes-pratiques-liees-au-pacte",
    ),
]
