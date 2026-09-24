"""URLs de depart Bpifrance Creation pour la collecte web du domaine `statuts`
(guide pratique de redaction, distinct de `statuts_societe` qui est le texte
de loi brut deja collecte via Legifrance -- voir
scrapers/legifrance/blocs_formes_juridiques.py, bloc L.210-1 a L.210-12).

Verifie manuellement le 24/09/2026 (WebFetch reel) : la page existe, contenu
extrait coherent (clauses obligatoires, points de vigilance SARL/SAS,
exemples de redaction pour le capital et les depots de fonds)."""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed

NOM_SOURCE = "Bpifrance Creation"
DOMAINE = "statuts"

PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(
        url="https://bpifrance-creation.fr/encyclopedie/formalites-creation-dune-entreprise/formalites-specifiques-a-creation-societes/points",
    ),
]
