"""Pages Bpifrance Création sur les journaux d'annonces légales (service
1.1.5, copilot). Pure donnée — fichier distinct de `pages_assurance.py`
(liste indépendante, SRP).

Vérifié le 25/09/2026 : la page existe ; couvre le rôle des JAL, les types
d'annonces, l'habilitation par arrêté préfectoral et comment trouver un
journal habilité.
"""
from scrapers.shared.guide_page import GuidePage

NOM_SOURCE = "Bpifrance Création"

PAGES: list[GuidePage] = [
    GuidePage(
        url="https://bpifrance-creation.fr/journal-dannonces-legales",
        sous_theme="choix_journal",
    ),
]
