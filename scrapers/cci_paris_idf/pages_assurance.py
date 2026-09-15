"""URLs de depart CCI Paris Ile-de-France pour la collecte web du volet
non-legal (service 1.1.10). Pure donnee.

Note : c'est la CCI Paris Ile-de-France precisement (entreprises.cci-paris-idf.fr),
pas "CCI France" en general — nom de dossier volontairement precis plutot
qu'un "cci_france" trop large pour une seule chambre regionale collectee.

Verifie manuellement le 2026-09-11 : la page cite explicitement l'obligation
d'assurance RC Pro pour les agents immobiliers (loi Hoguet) — "La personne
doit justifier de l'existence d'un contrat d'assurance couvrant les
consequences pecuniaires de sa responsabilite civile professionnelle (RCP)."
"""
from scrapers.shared.page_seed import PageSeed

NOM_SOURCE = "CCI Paris Ile-de-France"

PAGES: list[PageSeed] = [
    PageSeed(
        url="https://www.entreprises.cci-paris-idf.fr/fiches-pratiques/les-conditions-dobtention-dune-carte-professionnelle-loi-hoguet",
        secteurs_cibles=["Construction Tech / PropTech"],
        max_liens_a_suivre=3,
    ),
]
