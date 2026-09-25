"""URLs de depart Guichet unique (formalites.entreprises.gouv.fr, gere par
l'INPI) pour la collecte web du domaine `pre_depot` (agent reglementaire,
Increment 1). Pure donnee — voir `scrapers/bpifrance/pages_pacte_fondateurs.py`
pour le meme pattern.

Verifie manuellement le 24/09/2026 (WebFetch reel) : les 3 pages existent,
contenu extrait coherent (faq.php : suivi/delais/SIREN-Kbis, ne couvre PAS
les motifs de rejet en detail, voir domaine `rejet` volontairement absent du
perimetre de collecte -- decision actee en conversation, pas de contenu
public substantiel a indexer pour ce domaine ; declarer.php : preparation au
depot, signature electronique, publication de l'adresse ; suivre.php :
tableau de bord, statuts possibles d'une formalite)."""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed

NOM_SOURCE = "Guichet unique (INPI)"
DOMAINE = "pre_depot"

PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(url="https://formalites.entreprises.gouv.fr/faq.php"),
    AdministrativeGuideSeed(url="https://formalites.entreprises.gouv.fr/declarer.php"),
    AdministrativeGuideSeed(url="https://formalites.entreprises.gouv.fr/suivre.php"),
]
