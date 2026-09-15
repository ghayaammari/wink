"""Client API PI — Base Marques INPI. Communique avec l'API, rien d'autre
(même séparation que legifrance_client.py : aucune notion de service 1.1.x ici).

Nécessite un compte personnel sur https://data.inpi.fr (identifiant/mot de
passe) — voir INPI_USERNAME/INPI_PASSWORD dans .env.example. Gratuit, mais pas
une simple clé API à générer : c'est un compte utilisateur.

Ce qui est VÉRIFIÉ — testé de bout en bout le 2026-09-12 (compte réel
data.inpi.fr, auth + recherche + réponse effective, voir échange du 2026-09-12) :

- Authentification (doc technique officielle "Inpi_doc_tech_API_PI_v1.0_0.pdf") :
  1. GET https://api-gateway.inpi.fr/services/uaa/api/authenticate : pose un
     cookie `XSRF-TOKEN` (protection CSRF façon Spring Security), sans
     lui-même authentifier. `requests.Session` le conserve automatiquement.
  2. POST /auth/login, body {"username", "password", "rememberMe": true}, ET
     le token CSRF de l'étape 1 renvoyé À LA FOIS en header `X-XSRF-TOKEN` et
     en cookie explicite (la doc précise que le header seul ne suffit pas
     toujours). Pose en retour les cookies `access_token`/`session_token`
     (portés eux aussi automatiquement par `session` ensuite).
  3. Chaque appel authentifié suivant (ex: /marques/search) doit renvoyer le
     même header `X-XSRF-TOKEN` : contrairement aux cookies, un header n'est
     PAS reporté automatiquement d'une requête à l'autre par `requests.Session`
     — d'où le retour du token par `_login()` ci-dessous, repassé explicitement
     à `search_marque_status`.

- Recherche : POST /services/apidiffusion/api/marques/search, body :
      {"collections": ["FR", "EU", "WO"], "query": "[Mark=\"<nom>\"]",
       "fields": ["ApplicationNumber", "Mark", "MarkCurrentStatusCode", "DEPOSANT", "ukey"],
       "position": 0, "size": 10,
       "sortList": ["APPLICATION_DATE DESC", "MARK ASC"],
       "facetsList": ["APPLICANT", "CLASSIFICATION"],
       "withCTMRevendication": false, "withFacets": true}
  IMPORTANT — `nom` DOIT être entre guillemets dans la requête :
  `[Mark=Jouve Immobilier]` (sans guillemets) est une recherche plein texte
  très large (12 404 résultats observés pour "Jouve Immobilier" !) qui traite
  chaque mot indépendamment — avec `size=10` trié par date, la vraie marque
  "JOUVE IMMOBILIER" enregistrée peut ne jamais apparaître dans la page
  retournée => faux négatif "disponible" dangereux, observé en test réel le
  2026-09-12. `[Mark="Jouve Immobilier"]` (avec guillemets) fait une recherche
  par phrase exacte : count=1, la bonne marque, trouvée à tous les coups.
  Confirmé par test réel — ne jamais repasser à la syntaxe sans guillemets.

- Format de réponse : **JSON** avec `Accept: application/json` explicite (voir
  `_login`/`search_marque_status`). Piège observé : le serveur renvoie parfois
  la MÊME donnée en XML avec un header `Content-Type: application/xml` même
  quand le corps réel est du JSON (Swagger "Try it out", qui envoie son propre
  `Accept`, a montré du XML ; notre appel avec `Accept: application/json`
  renvoie du JSON) — ne jamais se fier au `Content-Type` retourné, seul
  l'`Accept` envoyé compte. Structure JSON :
      {"metadata": {...}, "results": [
        {"documentId": "...", "fields": [
           {"name": "Mark", "value": "...", "values": null},
           {"name": "MarkCurrentStatusCode", "value": "...", "values": null},
           ...
        ]}, ...
      ]}
  Un champ porte soit `value` (chaîne), soit `values` (liste, ex: DEPOSANT à
  plusieurs titulaires) — géré par `_field_text`.

  Statuts `MarkCurrentStatusCode` observés : "Marque enregistrée", "Marque
  renouvelée" (considérés bloquants ici), "Registered" (marques EU/WO, en
  anglais, bloquant), "Marque expirée" (non bloquant), "Demande publiée"
  (dépôt en cours, pas encore enregistré — actuellement PAS considéré comme
  bloquant, voir _STATUTS_BLOQUANTS ci-dessous : une demande en cours identique
  au nom testé n'est donc ni "pris" ni "risque" avec ce choix. Décision produit
  à trancher : une demande publiée peut aboutir à un enregistrement plus tard,
  donc représenter un vrai risque — mais ce n'est pas encore un droit acquis.
  Si ce cas doit compter comme "risque", ajouter son fold() à _STATUTS_BLOQUANTS
  avec une distinction "risque garanti" vs "pris" — pas fait ici pour ne pas
  inventer une règle métier non demandée).

**Dette technique assumée** : le flow (auth + recherche + parsing) est
confirmé par un appel réel réussi, mais pas testé sur la durée — durée de
validité de la session, comportement au renouvellement (401/403 après un
moment) toujours pas observés. Pas de cache de session entre appels pour
l'instant (une connexion complète par appel à `search_marque_status`) : à
optimiser seulement si la latence ou le rate-limiting posent problème en usage
réel, pas avant.
"""
import os

import requests

from scrapers.shared.text_normalize import fold

_AUTHENTICATE_URL = "https://api-gateway.inpi.fr/services/uaa/api/authenticate"
_LOGIN_URL = "https://api-gateway.inpi.fr/auth/login"
_SEARCH_URL = "https://api-gateway.inpi.fr/services/apidiffusion/api/marques/search"

# Statuts INPI valant occupation réelle de la marque — voir docstring module
# (le cas "Demande publiée" est une décision produit à trancher, pas incluse
# ici par défaut). Comparés via fold() (accents/casse ignorés), d'où
# l'écriture sans accents.
_STATUTS_BLOQUANTS = {fold("Marque enregistrée"), fold("Marque renouvelée"), fold("Registered")}


class InpiApiError(Exception):
    """Échec d'authentification ou d'appel à l'API Base Marques INPI."""


def _login(session: requests.Session) -> str:
    """Authentifie `session` auprès de l'INPI (voir docstring module pour le
    détail des 3 étapes) et retourne le token CSRF à repasser en header
    `X-XSRF-TOKEN` sur les appels authentifiés suivants.
    """
    username = os.environ.get("INPI_USERNAME")
    password = os.environ.get("INPI_PASSWORD")
    if not username or not password:
        raise InpiApiError("INPI_USERNAME / INPI_PASSWORD manquants dans .env.")

    # Étape 1 : obtenir le cookie CSRF (XSRF-TOKEN) avant tout login.
    try:
        session.get(_AUTHENTICATE_URL, timeout=20)
    except requests.RequestException as exc:
        raise InpiApiError(f"Échec réseau vers l'initialisation CSRF INPI : {exc}") from exc

    csrf_token = session.cookies.get("XSRF-TOKEN")
    if not csrf_token:
        raise InpiApiError(
            "Cookie XSRF-TOKEN absent après l'appel à /authenticate — le flux "
            "d'authentification INPI a probablement changé, voir docstring module."
        )

    # Étape 2 : login, token CSRF renvoyé en header ET en cookie explicite.
    try:
        response = session.post(
            _LOGIN_URL,
            json={"username": username, "password": password, "rememberMe": True},
            headers={"Accept": "application/json, text/plain, */*", "X-XSRF-TOKEN": csrf_token},
            cookies={"XSRF-TOKEN": csrf_token},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InpiApiError(f"Échec réseau vers l'authentification INPI : {exc}") from exc

    if response.status_code != 200:
        raise InpiApiError(f"Échec d'authentification INPI ({response.status_code}) : {response.text}")

    return csrf_token


def search_marque_status(nom: str) -> str:
    """Retourne "disponible" / "risque" / "pris" pour le nom donné.

    Une nouvelle session (login + requête) par appel — pas de cache de token
    entre appels pour l'instant (voir "Dette technique assumée" en tête de
    fichier).
    """
    session = requests.Session()
    csrf_token = _login(session)

    # Guillemets obligatoires : recherche par phrase exacte, pas plein texte
    # — voir avertissement en tête de fichier (faux négatif "disponible"
    # observé sans guillemets). Les `"` du nom lui-même sont retirés avant
    # insertion pour ne pas fermer la phrase prématurément côté INPI (aucun
    # nom d'entreprise/marque légitime n'en contient).
    nom_recherche = nom.replace('"', "")

    try:
        response = session.post(
            _SEARCH_URL,
            json={
                "collections": ["FR", "EU", "WO"],
                "query": f'[Mark="{nom_recherche}"]',
                "fields": ["ApplicationNumber", "Mark", "MarkCurrentStatusCode", "DEPOSANT", "ukey"],
                "position": 0,
                "size": 10,
                "sortList": ["APPLICATION_DATE DESC", "MARK ASC"],
                "facetsList": ["APPLICANT", "CLASSIFICATION"],
                "withCTMRevendication": False,
                "withFacets": True,
            },
            # X-XSRF-TOKEN : le cookie est reporté automatiquement par
            # `session`, mais le header doit être repassé explicitement à
            # chaque appel (voir docstring module, étape 3). Accept : demande
            # explicitement du JSON — voir avertissement sur le Content-Type
            # trompeur renvoyé par le serveur.
            headers={"X-XSRF-TOKEN": csrf_token, "Accept": "application/json"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InpiApiError(f"Échec réseau vers la recherche de marques INPI : {exc}") from exc

    if response.status_code != 200:
        raise InpiApiError(f"Échec de recherche de marque ({response.status_code}) : {response.text}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise InpiApiError(
            f"Réponse INPI illisible (JSON invalide) : {exc} — début du corps={response.text[:300]!r}"
        ) from exc

    return _parse_marque_status(payload, nom)


def _field_text(field: dict) -> str:
    """Un champ JSON porte soit `value` (chaîne), soit `values` (liste, ex:
    DEPOSANT à plusieurs titulaires) — on ne prend que le premier élément
    dans ce second cas, suffisant pour Mark/MarkCurrentStatusCode qui n'ont
    jamais plusieurs valeurs en pratique.
    """
    value = field.get("value")
    if value:
        return value
    values = field.get("values")
    if values:
        return values[0]
    return ""


def _parse_marque_status(payload: dict, nom: str) -> str:
    """Format confirmé par appel réel le 2026-09-12 — voir docstring module.
    Une marque au statut bloquant (_STATUTS_BLOQUANTS) dont le libellé
    correspond exactement (casse/accents ignorés) => "pris". Une
    correspondance partielle (le nom testé apparaît dans un libellé plus
    long, ou l'inverse) => "risque", signal seulement. Sinon "disponible".
    """
    nom_normalise = fold(nom)

    exact_match = False
    partial_match = False
    for result in payload.get("results") or []:
        mark = statut = ""
        for field in result.get("fields") or []:
            name = field.get("name")
            if name == "Mark":
                mark = _field_text(field)
            elif name == "MarkCurrentStatusCode":
                statut = _field_text(field)

        if fold(statut) not in _STATUTS_BLOQUANTS:
            continue  # marque expirée/en cours de dépôt/etc. : pas de conflit acté

        mark_normalise = fold(mark)
        if mark_normalise == nom_normalise:
            exact_match = True
        elif nom_normalise in mark_normalise or mark_normalise in nom_normalise:
            partial_match = True

    if exact_match:
        return "pris"
    if partial_match:
        return "risque"
    return "disponible"
