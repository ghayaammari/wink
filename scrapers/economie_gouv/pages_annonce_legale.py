"""URLs de depart economie.gouv.fr (Ministere de l'Economie) pour la collecte
web du domaine `annonce_legale` (agent reglementaire, Increment 1). Guide
officiel sur la PROCEDURE de publication -- distinct de BODACC (API de
consultation des annonces DEJA publiees, par entreprise precise) : BODACC
n'est pas un contenu a indexer semantiquement, c'est une donnee factuelle par
SIREN, hors perimetre de collecte ici (voir remarque a l'equipe -- meme
raisonnement que `rejet`, ecarte du corpus).

Verifie manuellement le 24/09/2026 (WebFetch reel) : la page existe, contenu
extrait coherent (obligation de publication avant immatriculation, tarifs
standardises 121-387 EUR, mentions obligatoires de l'annonce)."""
from scrapers.shared.administrative_guide_seed import AdministrativeGuideSeed

NOM_SOURCE = "economie.gouv.fr"
DOMAINE = "annonce_legale"

PAGES: list[AdministrativeGuideSeed] = [
    AdministrativeGuideSeed(
        url="https://www.economie.gouv.fr/entreprises/creer-une-entreprise/creation-dentreprise-comment-publier-une-annonce-legale",
    ),
]
