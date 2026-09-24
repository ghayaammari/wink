"""Pages economie.gouv.fr sur l'annonce légale (service 1.1.5, copilot).
Pure donnée.

Vérifié le 25/09/2026 : la page existe ; couvre la définition, l'obligation
(exceptions EI / micro-entreprise), le journal habilité du département, le
contenu et la tarification forfaitaire.
"""
from scrapers.shared.guide_page import GuidePage

NOM_SOURCE = "economie.gouv.fr"

PAGES: list[GuidePage] = [
    GuidePage(
        url="https://www.economie.gouv.fr/entreprises/creer-une-entreprise/creation-dentreprise-comment-publier-une-annonce-legale",
        sous_theme="general",
    ),
]
