"""URLs de depart Guichet unique (formalites.entreprises.gouv.fr, gere par
l'INPI) pour la collecte web du domaine `tarifs` (agent reglementaire,
Increment 1). Source officielle prefere a Infogreffe (page commerciale) --
meme source de confiance que `pre_depot`, voir pages_pre_depot.py.

Verifie manuellement le 24/09/2026 (WebFetch reel) : la page existe, contenu
extrait coherent (grille tarifaire RNE/INPI, RCS, agents commerciaux,
entreprises agricoles, en vigueur au 1er mars 2026)."""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed

NOM_SOURCE = "Guichet unique (INPI)"
DOMAINE = "tarifs"

PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(url="https://formalites.entreprises.gouv.fr/tarifs.php"),
]
