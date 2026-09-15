"""Client API "Recherche d'Entreprises" (recherche-entreprises.api.gouv.fr) —
communique avec l'API, rien d'autre. Publique, gratuite, sans authentification,
pas de clé à configurer.

Dossier séparé (et non code direct dans le service 1.1.2) car cette source est
réutilisée par plusieurs services indépendants (voir Wink_architecture_fichiers.md,
règle "scrapers organisé par source externe, pas par service") : 1.1.2 ici pour
la dénomination, et plus tard 1.1.9/1.1.19 pour le statut d'immatriculation/Kbis
— même endpoint que celui déjà validé dans la spec Parcours B (page Notion
"Wink — Scénario détaillé : Informations légales, startup déjà créée").

Confirmé par appel réel (premier test en conditions réelles, SIREN Doctolib
794598813) : l'endpoint `/search`, la clé racine `results`, et les champs
`nom_complet`/`nom_raison_sociale` + `etat_administratif` (`"A"` = actif) au
niveau racine de chaque résultat.

**Piège rencontré et corrigé :** `q=siren:123456782` (syntaxe à préfixe,
reprise du README d'un autre repo public autour de cette API) NE FONCTIONNE
PAS — testé en réel, retourne 0 résultat pour un SIREN pourtant actif et
correct. L'API ne supporte pas de filtre par préfixe `champ:valeur` dans `q`.
La bonne syntaxe, confirmée par la doc OpenAPI officielle et par un appel réel
qui retourne bien la fiche : passer le SIREN/SIRET tel quel comme valeur de
`q`, sans préfixe :
    GET recherche-entreprises.api.gouv.fr/search?q=794598813
`with_etat_administratif=true` reste envoyé par cohérence avec `search_by_name`
mais n'est pas strictement nécessaire (`etat_administratif` est déjà présent
par défaut dans la réponse observée).
"""
import requests

from scrapers.shared.text_normalize import fold

_SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Valeur documentée pour une entreprise active — voir avertissement ci-dessus.
_ETAT_ACTIF = "A"


class RechercheEntreprisesApiError(Exception):
    """Échec d'appel à l'API Recherche d'Entreprises."""


def search_by_name(nom: str) -> list[dict]:
    """Recherche libre par nom. Retourne la liste brute des résultats (dicts),
    déjà limités aux entreprises actives côté API par `with_etat_administratif`
    (le champ reste présent dans chaque résultat, pas un filtre côté serveur —
    voir avertissement module : à reconfirmer).
    """
    try:
        response = requests.get(
            _SEARCH_URL,
            params={"q": nom, "with_etat_administratif": "true"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise RechercheEntreprisesApiError(f"Échec réseau vers Recherche d'Entreprises : {exc}") from exc

    if response.status_code != 200:
        raise RechercheEntreprisesApiError(
            f"Échec de recherche ({response.status_code}) : {response.text}"
        )
    payload = response.json()
    return payload.get("results", [])


def is_active_match(results: list[dict], nom_normalise: str) -> bool:
    """True si au moins un résultat actif correspond au nom normalisé (casse/
    accents ignorés — même logique de comparaison que Parcours B, voir
    `name_availability_service._normalize`).
    """
    for result in results:
        etat = result.get("etat_administratif")
        nom_complet = result.get("nom_complet") or result.get("nom_raison_sociale") or ""
        if etat == _ETAT_ACTIF and fold(nom_complet) == nom_normalise:
            return True
    return False


def get_by_siren(siren: str) -> dict | None:
    """Recherche exacte par SIREN. Retourne le premier résultat brut (dict) ou
    `None` si aucune entreprise ne correspond (format valide mais introuvable/
    inactive) — utilisé par la vérification SIREN/SIRET (Parcours B, appelée
    au clic sur "Mettre à jour") et plus tard par le job périodique de 1.1.9
    (Parcours A) — même endpoint.

    Le SIREN est passé tel quel comme valeur de `q`, SANS préfixe `siren:` —
    voir avertissement module : cette syntaxe à préfixe a été testée en réel
    et ne fonctionne pas (0 résultat sur un SIREN actif), corrigée après un
    premier test utilisateur qui a révélé le problème (tous les statuts
    restaient "non_verifie" même sur une entreprise réelle et active).
    """
    try:
        response = requests.get(
            _SEARCH_URL,
            params={"q": siren, "with_etat_administratif": "true"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise RechercheEntreprisesApiError(f"Échec réseau vers Recherche d'Entreprises : {exc}") from exc

    if response.status_code != 200:
        raise RechercheEntreprisesApiError(
            f"Échec de recherche ({response.status_code}) : {response.text}"
        )
    results = response.json().get("results", [])
    return results[0] if results else None
