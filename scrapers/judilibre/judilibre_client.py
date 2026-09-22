"""Client API Judilibre (Cour de cassation) -- nouvelle source (25/09/2026,
service 1.1.13 categorie 3), separee de `scrapers/legifrance/` par
convention du repo ("scrapers/ organise par source, pas par service", voir
Wink_architecture_fichiers.md) : Judilibre est publie par une institution
differente (Cour de cassation, pas la DILA) mais transite par le MEME portail
PISTE que Légifrance, avec la MEME authentification.

CORRECTION du 22/09/2026 (bug reel, confirme par appel authentique via
diag_judilibre.py) : la doc textuelle de judilibre-search annonce une auth
par simple cle API (header "KeyId"), mais un vrai appel avec ce header seul
echoue (400, corps vide). Un appel OAuth2 client_credentials avec les MEMES
identifiants que Légifrance (LEGIFRANCE_CLIENT_ID/SECRET) reussit (200,
resultats corrects). Conclusion : sur le portail PISTE, Judilibre est
protege par la meme auth applicative OAuth2 que Légifrance -- le header
KeyId documente ailleurs ne s'applique pas (ou plus) a ce portail. Ce
client reutilise donc directement `_get_token()` de legifrance_client.py
(meme token, meme cache process, pas de logique dupliquee) plutot que de
lire JUDILIBRE_API_KEY.

Ce qui reste VERIFIE (documentation publique du depot Cour-de-cassation/
judilibre-search, lu le 25/09/2026) :
- base URL prod : https://api.piste.gouv.fr/cassation/judilibre/v1.0
- endpoint recherche : GET /search (parametres : query, field, chamber,
  jurisdiction, theme...)
- endpoint decision complete : GET /decision (parametre : id)

Ce qui est maintenant VERIFIE par de vrais appels (22/09/2026) :
- /search (query="brevet") : champs reels par resultat : id, jurisdiction,
  chamber, number, numbers, ecli, publication, decision_date, solution,
  type, summary, themes, files, titlesAndSummaries, particularInterest
  (booleen, PAS une url), highlights (extraits surlignes, PAS le texte
  integral). AUCUN champ `text` ni `url` n'est present dans /search --
  l'hypothese initiale ("texte integral dans le champ text de /search",
  ligne ci-dessus dans la doc publique) etait FAUSSE, confirmee par une
  vraie erreur de collecte le 22/09/2026 (cles recues listees explicitement,
  pas de "text" dedans). L'ancien parsing url (`item.get("particularInterest")
  or item.get("url")`) etait lui aussi double-fautif (booleen pris pour une
  url, et le champ url n'existe simplement pas) -- corrige en url=None.
- /decision?id=<id> : c'est CE endpoint, pas /search, qui porte le texte
  integral, dans un champ `text` -- confirme par un client PISTE tiers
  reel (depot jmtanguy/DroitFrancaisMCP, api_judilibre.py, lu le 22/09/2026)
  qui construit l'appel ainsi : GET {base_url}/decision?id=<id>, meme
  auth Bearer OAuth2 que /search. search_decisions() fait donc 2 appels
  par resultat retenu : /search pour trouver les decisions pertinentes,
  puis /decision par id pour le texte integral -- un N+1 assume : script
  de collecte ponctuel (pas une boucle utilisateur), volume minuscule
  (3 requetes x taille=3 = 9 appels /decision au total pour ce service),
  et l'API ne propose pas d'endpoint batch pour /decision.
"""
import requests

from scrapers.legifrance.legifrance_client import LegifranceApiError, _get_token

_BASE_URL_PROD = "https://api.piste.gouv.fr/cassation/judilibre/v1.0"
_BASE_URL_SANDBOX = "https://sandbox-api.piste.gouv.fr/cassation/judilibre/v1.0"


class JudilibreApiError(Exception):
    """Echec d'authentification ou d'appel a l'API Judilibre."""


def _base_url() -> str:
    import os
    # JUDILIBRE_ENV=sandbox pour tester avec un token sandbox avant de passer
    # en production -- comportement par defaut = production.
    return _BASE_URL_SANDBOX if os.environ.get("JUDILIBRE_ENV") == "sandbox" else _BASE_URL_PROD


def _get(path: str, params: dict) -> dict:
    try:
        token = _get_token()
    except LegifranceApiError as exc:
        # _get_token() leve LegifranceApiError si LEGIFRANCE_CLIENT_ID/SECRET
        # manquent -- on relaie sous JudilibreApiError pour ne pas exposer un
        # type d'erreur "Legifrance" a un appelant Judilibre.
        raise JudilibreApiError(str(exc)) from exc

    response = requests.get(
        f"{_base_url()}{path}",
        params=params,
        headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
    )
    if response.status_code != 200:
        raise JudilibreApiError(f"Echec d'appel a {path} ({response.status_code}) : {response.text}")
    return response.json()


def _fetch_decision_text(decision_id: str) -> str:
    """Recupere le texte integral d'une decision via /decision?id=...
    (voir docstring module : /search ne porte PAS le texte integral, seul
    /decision l'a). Leve JudilibreApiError avec le detail des cles recues
    si le champ `text` est absent, plutot que de deviner un autre nom.
    """
    payload = _get("/decision", {"id": decision_id})
    texte = payload.get("text")
    if texte is None:
        raise JudilibreApiError(
            f"Reponse /decision (id={decision_id}) sans champ 'text' -- cles recues : {sorted(payload.keys())}."
        )
    return texte


def search_decisions(query: str, *, taille: int = 3, chamber: str | None = None) -> list[dict]:
    """Recherche les `taille` decisions les plus pertinentes pour `query`
    (tri par score de pertinence -- comportement par defaut annonce par la
    doc, non reconfigure ici). `chamber` optionnel (ex: "civ1", "comm") pour
    restreindre a une chambre -- non utilise par defaut, chaque appelant
    (requetes_pacte_fondateurs.py) precise ce qui est pertinent par requete.

    Pour chaque decision retenue par /search, un second appel /decision
    recupere le texte integral (voir docstring module -- /search ne le
    fournit pas). N+1 assume, volume minuscule, voir docstring module.

    Retourne une liste de dicts {numero_decision, texte_brut, date_decision,
    url} -- url toujours None pour l'instant, voir docstring module.
    """
    params: dict = {"query": query, "page_size": taille}
    if chamber:
        # "chamber" est de type "array (string)" cote API (voir swagger
        # public du depot judilibre-search) -- envoye en liste explicitement
        # (requests genere alors chamber=... repete si plusieurs valeurs)
        # plutot qu'une simple chaine, par coherence avec le type documente.
        params["chamber"] = [chamber]

    payload = _get("/search", params)
    resultats = payload.get("results")
    if resultats is None:
        raise JudilibreApiError(
            f"Reponse /search sans champ 'results' -- cles recues : {sorted(payload.keys())}."
        )

    decisions = []
    for item in resultats[:taille]:
        decision_id = item.get("id")
        numero = item.get("number") or decision_id
        if decision_id is None or numero is None:
            raise JudilibreApiError(
                f"Resultat /search sans 'id' ou 'number' -- cles recues : {sorted(item.keys())}."
            )
        texte = _fetch_decision_text(decision_id)
        decisions.append({
            "numero_decision": str(numero),
            "texte_brut": texte,
            "date_decision": item.get("decision_date"),
            "url": None,
        })
    return decisions
