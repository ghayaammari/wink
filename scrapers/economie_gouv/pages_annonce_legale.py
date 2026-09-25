"""Sources economie.gouv.fr pour l'annonce légale.

Deux interfaces sont conservées pour les deux pipelines :
- `PAGES` utilise par l'ancien collecteur de guides d'annonce légale ;
- `ADMINISTRATIVE_PAGES` utilise par le collecteur administratif moderne.
"""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed
from scrapers.shared.guide_page import GuidePage

NOM_SOURCE = "economie.gouv.fr"
DOMAINE = "annonce_legale"

_URL = "https://www.economie.gouv.fr/entreprises/creer-une-entreprise/creation-dentreprise-comment-publier-une-annonce-legale"

# Interface historique : collect_legal_announcement_guides.py.
PAGES: list[GuidePage] = [
    GuidePage(
        url=_URL,
        sous_theme="general",
    ),
]

# Interface administrative : collect_administrative_guides.py.
ADMINISTRATIVE_PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(
        url=_URL,
    ),
]
