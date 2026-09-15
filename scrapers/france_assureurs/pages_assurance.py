"""URLs de depart France Assureurs (FFA) pour la collecte web du volet
non-legal (service 1.1.10). Pure donnee — le contenu reel est recupere a
l'execution par `scrapers/shared/web_fetch.py::fetch_page()`.

Verifie manuellement le 2026-09-11 :
- Le PDF est accessible (200, application/pdf) et son extraction via pypdf
  produit un vrai contenu coherent avec le titre annonce ("15 reflexes pour
  bien s'assurer" — locaux/materiel, mobilite, RC pro, cyber, sante/prevoyance).
- La page presse (HTML) qui l'annonce n'a que peu de contenu propre (surtout
  un lien vers le PDF) mais reste incluse comme URL de depart : le crawling
  borne peut y decouvrir d'autres guides de la meme collection.
"""
from scrapers.shared.page_seed import PageSeed

NOM_SOURCE = "France Assureurs"

PAGES: list[PageSeed] = [
    PageSeed(
        url="https://www.franceassureurs.fr/wp-content/uploads/240312__france-assureurs_15-reflexes-entreprises__digital.pdf",
        secteurs_cibles=[
            "SaaS / Tech generique",
            "E-commerce / Marketplace",
            "Mobilite / Transport / Logistique",
            "Industrie / Manufacturing",
            "Conseil / Services professionnels",
        ],
        max_liens_a_suivre=0,  # PDF : pas de graphe de liens a suivre
    ),
    PageSeed(
        url="https://www.franceassureurs.fr/espace-presse/france-assureurs-publie-son-guide-pratique-pour-les-entrepreneurs-15-reflexes-pour-bien-sassurer/",
        secteurs_cibles=[
            "SaaS / Tech generique",
            "E-commerce / Marketplace",
            "Conseil / Services professionnels",
        ],
        max_liens_a_suivre=5,
    ),
]
