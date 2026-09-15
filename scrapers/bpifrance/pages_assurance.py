"""URLs de depart Bpifrance Creation pour la collecte web du volet non-legal
(service 1.1.10). Pure donnee — le contenu reel est recupere a l'execution
par `scrapers/shared/web_fetch.py::fetch_page()`, jamais ecrit ici.

Verifie manuellement le 2026-09-11 : la page existe, repond 200, contenu
extrait coherent (guide general sur l'assurance d'entreprise).
"""
from scrapers.shared.page_seed import PageSeed

NOM_SOURCE = "Bpifrance Creation"

PAGES: list[PageSeed] = [
    PageSeed(
        url="https://bpifrance-creation.fr/moment-de-vie/assurer-mon-entreprise",
        secteurs_cibles=[
            "SaaS / Tech generique",
            "E-commerce / Marketplace",
            "Conseil / Services professionnels",
        ],
        max_liens_a_suivre=8,
    ),
]
