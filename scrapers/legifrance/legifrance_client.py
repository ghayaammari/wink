"""Client API PISTE/Légifrance — communique avec l'API, rien d'autre (aucune
notion de legal_texts, aucun LLM). Auth OAuth2 client_credentials (client_id/
secret dans .env), token mis en cache en mémoire process et renouvelé à
expiration.

Ce qui est VÉRIFIÉ (documenté publiquement, cohérent entre plusieurs clients
open-source PISTE/Légifrance) :
- endpoint de token : https://oauth.piste.gouv.fr/api/oauth/token, grant_type=
  client_credentials, scope=openid
- base API : https://api.piste.gouv.fr/dila/legifrance/lf-engine-app
- endpoint article unique : POST consult/getArticle {"id": ...}
- endpoint texte consolidé (code/loi) : POST consult/legiPart {"textId": ...,
  "date": ...}

Ce qui est VÉRIFIÉ par un vrai appel authentifié (test du 10/09/2026, sur le
bloc SAS/SASU) :
- `consult/legiPart` IGNORE un identifiant de section (LEGISCTA) passé en
  `textId` : il renvoie toujours le texte ENTIER (testé avec la section
  SAS/SASU → réponse = tout le Code de commerce, 7334 articles, 51 Mo). Donc
  UN SEUL appel par texte source (Code de commerce, Code civil, une loi...),
  jamais un appel par section/bloc — voir _fetch_text() et son cache ci-dessous.
- dans la réponse, chaque article a bien son texte intégral (champ `content`,
  pas `texte`) — pas besoin d'appel getArticle supplémentaire.
- les sections sont bien imbriquées et retrouvables par leur `id`/`cid`
  (ex: LEGISCTA000006146048 → "Chapitre VII : Des sociétés par actions
  simplifiées", 23 articles, conforme à L227-1 -> L227-20-1) — c'est ce qui
  permet d'extraire localement la bonne section après un seul fetch du texte
  entier, voir _find_section() ci-dessous.
- chaque article a un champ `etat` (ex: "VIGUEUR", "ABROGE"...) — on ne garde
  que les articles en vigueur : un article abrogé n'a pas d'intérêt pour un
  entrepreneur qui crée sa société aujourd'hui.

Ce qui N'EST TOUJOURS PAS vérifié :
- l'identifiant LEGITEXT de la Loi n°78-763 du 19/07/1978 (SCOP) et le
  traitement des articles CGI non contigus (micro-entreprise) — voir
  blocs_formes_juridiques.py, ces 2 blocs sont volontairement laissés vides.
"""
import os
import re
import time
from datetime import date as date_type, datetime, timedelta, timezone
from html import unescape

import requests

# PISTE a 2 environnements sur des DOMAINES DIFFERENTS (pas juste une variable
# d'URL) — une application/des cles creees en sandbox echouent en production
# et inversement ("invalid_client", constate en pratique le 16/09/2026 avec
# une cle sandbox appelee contre les hotes production ci-dessous). Verifie
# via la page officielle "PISTE URL decommissioning" (migration effective du
# 30/09/2023, domaines confirmes) :
#   production : oauth.piste.gouv.fr        / api.piste.gouv.fr
#   sandbox    : sandbox-oauth.piste.gouv.fr / sandbox-api.piste.gouv.fr
# LEGIFRANCE_ENV bascule les deux en une fois plutot que 2 variables separees
# (elles vont toujours ensemble, jamais token prod + API sandbox ou l'inverse).
_LEGIFRANCE_ENV = os.environ.get("LEGIFRANCE_ENV", "sandbox").strip().lower()

if _LEGIFRANCE_ENV == "production":
    _TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
    _API_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
elif _LEGIFRANCE_ENV == "sandbox":
    _TOKEN_URL = "https://sandbox-oauth.piste.gouv.fr/api/oauth/token"
    _API_BASE = "https://sandbox-api.piste.gouv.fr/dila/legifrance/lf-engine-app"
else:
    # ValueError, pas LegifranceApiError : cette classe est definie plus bas
    # dans ce module, une erreur de config au chargement du module ne peut
    # pas encore la referencer (leve avant sa definition).
    raise ValueError(
        f"LEGIFRANCE_ENV='{_LEGIFRANCE_ENV}' invalide — attendu 'sandbox' ou 'production'."
    )

_token: str | None = None
_token_expires_at: float = 0.0

# Cache en mémoire process du texte entier par legifrance_source_id — évite de
# retélécharger 51 Mo à chaque bloc quand plusieurs blocs partagent le même
# texte source (9 blocs pour le seul Code de commerce, voir docstring module).
_text_cache: dict[tuple[str, str], dict] = {}


class LegifranceApiError(Exception):
    """Échec d'authentification ou d'appel à l'API Légifrance."""


def _get_token() -> str:
    global _token, _token_expires_at
    if _token is not None and time.time() < _token_expires_at:
        return _token

    client_id = os.environ.get("LEGIFRANCE_CLIENT_ID")
    client_secret = os.environ.get("LEGIFRANCE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise LegifranceApiError("LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET manquants dans .env.")

    response = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "openid",
        },
    )
    if response.status_code != 200:
        raise LegifranceApiError(f"Échec d'authentification PISTE ({response.status_code}) : {response.text}")

    payload = response.json()
    _token = payload["access_token"]
    _token_expires_at = time.time() + payload.get("expires_in", 3600) - 60
    return _token


def _post(path: str, body: dict) -> dict:
    token = _get_token()
    response = requests.post(
        f"{_API_BASE}/{path}",
        json=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    if response.status_code != 200:
        raise LegifranceApiError(f"Échec d'appel à {path} ({response.status_code}) : {response.text}")
    return response.json()


# CORRECTIF du 17/09/2026 — consult/legiPart est reserve au fonds LEGI (les
# Codes) : un textId LEGITEXT d'une Loi (fonds LODA, ex: Loi n78-17) s'y fait
# rejeter en 403 meme s'il est du bon type LEGITEXT (les deux fonds partagent
# ce prefixe d'id mais pas le meme endpoint de consultation). Cause reelle du
# 403 constate sur la collecte RGPD le 17/09/2026 - au debut attribue a tort a
# un mauvais id (JORFTEXT au lieu de LEGITEXT, corrige separement), alors que
# l'id LEGITEXT correct echouait aussi pour cette veritable raison. Voir
# fetch_articles_in_text(fonds=...) plus bas.
_ENDPOINT_PAR_FONDS = {
    "LEGI": "consult/legiPart",
    "LODA": "consult/lawDecree",
}


def _fetch_text(legifrance_source_id: str, *, date: str | None = None, fonds: str = "LEGI") -> dict:
    """Récupère le texte entier (code ou loi/décret selon `fonds`), mis en
    cache par (fonds, legifrance_source_id) — voir docstring du module : un
    identifiant de section n'est pas accepté en entrée, seul le texte entier
    l'est.

    `fonds` choisit l'endpoint PISTE : "LEGI" (défaut, Codes) -> consult/
    legiPart, "LODA" (Lois/Ordonnances/Décrets/Arrêtés) -> consult/lawDecree.
    Le corps de requête est identique dans les deux cas ({"textId", "date"}).

    Forme de la réponse de consult/lawDecree (racine avec `articles`/`sections`
    directement, comme consult/legiPart) : PAS ENCORE vérifiée par un vrai
    appel au moment de l'écriture (17/09/2026) — seul consult/legiPart l'a été
    (test du 10/09/2026, Code de commerce). Si `fetch_articles_in_text(...,
    fonds="LODA")` renvoie une liste vide de façon suspecte, vérifier ici en
    premier : la réponse est peut-être enveloppée différemment (ex: sous une
    clé `text` ou `article` plutôt qu'à la racine).

    `date` par défaut = aujourd'hui, jamais omis : un premier essai sans date
    a échoué avec une erreur 500 côté serveur PISTE (message générique,
    "exception non gérée") sur le Code de commerce — le schéma officiel de
    consult/legiPart prévoit ce champ, et on veut de toute façon la version en
    vigueur aujourd'hui (cohérent avec le filtre etat="VIGUEUR" plus bas).
    """
    cache_key = (fonds, legifrance_source_id)
    if cache_key in _text_cache:
        return _text_cache[cache_key]

    endpoint = _ENDPOINT_PAR_FONDS.get(fonds)
    if endpoint is None:
        raise LegifranceApiError(f"fonds '{fonds}' inconnu — attendu 'LEGI' ou 'LODA'.")

    body = {"textId": legifrance_source_id, "date": date or date_type.today().isoformat()}
    payload = _post(endpoint, body)
    _text_cache[cache_key] = payload
    return payload


def _find_section(node: dict, section_id: str) -> dict | None:
    """Cherche récursivement, dans l'arbre `sections` d'un texte déjà récupéré,
    le nœud dont `id` ou `cid` correspond à section_id. Retourne le texte
    entier lui-même si section_id le désigne directement (bloc = texte entier,
    ex: Loi du 1er juillet 1901).
    """
    if node.get("id") == section_id or node.get("cid") == section_id:
        return node
    for section in node.get("sections") or []:
        found = _find_section(section, section_id)
        if found is not None:
            return found
    return None


_EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _millis_to_date(millis: float) -> date_type:
    """Convertit un timestamp en millisecondes en date, sans passer par

    `datetime.fromtimestamp()` — CORRECTIF du 18/09/2026 : cette fonction
    plante avec `OSError: [Errno 22] Invalid argument` sous Windows pour tout
    timestamp negatif (date antérieure au 01/01/1970), constaté en pratique
    sur un article de la Constitution du 4 octobre 1958 (dateDebut négatif).
    `EPOCH_UTC + timedelta(...)` fonctionne pour n'importe quelle date, sur
    toute plateforme — les textes juridiques français remontent bien avant
    1970 (cette Constitution en est un exemple direct), donc les timestamps
    négatifs ne sont pas un cas rare à ignorer.
    """
    return (_EPOCH_UTC + timedelta(milliseconds=millis)).date()


def _parse_legifrance_date(value) -> date_type | None:
    """Légifrance renvoie ses dates en millisecondes depuis 1970 (ex: dateDebut

    = 969494400000), pas en texte lisible — vu en pratique sur un vrai appel
    (erreur `cannot cast type bigint to date` avant cette conversion). Gère
    aussi une chaîne ISO par prudence, au cas où un autre champ l'utilise.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return _millis_to_date(value)
    if isinstance(value, str):
        if value.lstrip("-").isdigit():
            return _millis_to_date(int(value))
        try:
            return date_type.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


_HTML_TAG_RE = re.compile(r"<[^>]+>")

# BUG RÉEL corrigé le 10/09/2026 (constaté sur L.227-10, article à 4 alinéas
# séparés par des <p>) : retirer directement les balises sans distinction
# collait les alinéas entre eux ("...L. 233-3.Les associés statuent...", sans
# espace ni saut de ligne), cassant le découpage par alinéa de la Phase 2
# (chunking_suggere="par_alinea") même sur les articles où le LLM avait bien
# détecté des sujets distincts. Il faut donc remplacer les frontières de bloc
# (`</p>`, `<br>`) par un saut de ligne AVANT de retirer le reste des balises.
_BLOCK_BOUNDARY_RE = re.compile(r"</p\s*>|<br\s*/?>", re.IGNORECASE)


def strip_html(raw: str) -> str:
    """Nettoie le HTML renvoyé par Légifrance dans `content` (Étape 1.2 du
    plan Notion — extraction de champ, pas de la structuration, donc fait ici
    plutôt que par un appel LLM). Remplace les frontières de bloc (`</p>`,
    `<br>`) par un double saut de ligne AVANT de retirer les autres balises
    (`<a href=...>L. 210-10</a>` devient juste "L. 210-10", le lien est perdu
    mais on n'en a pas l'usage actuellement — voir discussion) — sinon deux
    alinéas se retrouvent collés sans aucune frontière (voir _BLOCK_BOUNDARY_RE
    ci-dessus). Décode ensuite les entités HTML (&eacute; etc.) et normalise
    les espaces/sauts de ligne en trop.

    Publique (pas de préfixe `_`) : réutilisable par un futur script de
    correction rétroactive sans refaire d'appel Légifrance/Groq — un appel
    réseau (le vrai coût de la collecte) ne doit pas devenir la seule façon
    d'obtenir un texte propre.
    """
    text = _BLOCK_BOUNDARY_RE.sub("\n\n", raw)
    text = _HTML_TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _collect_articles(node: dict) -> list[dict]:
    """Collecte récursivement tous les articles en vigueur (etat="VIGUEUR")
    sous un nœud (le nœud lui-même + ses sous-sections) — un article abrogé
    n'a pas d'intérêt pour la collecte (voir docstring du module).
    """
    articles: list[dict] = []

    def _collect(article: dict) -> None:
        if article.get("etat") != "VIGUEUR":
            return
        articles.append(
            {
                "article_numero": article.get("num"),
                "texte_brut": strip_html(article.get("content") or ""),
                "date_effet": _parse_legifrance_date(article.get("dateDebut")),
            }
        )

    def _walk(n: dict) -> None:
        for article in n.get("articles") or []:
            _collect(article)
        for section in n.get("sections") or []:
            _walk(section)

    _walk(node)
    return articles


def fetch_articles_in_block(
    legifrance_source_id: str, legifrance_section_id: str, *, date: str | None = None, fonds: str = "LEGI"
) -> list[dict]:
    """Récupère tous les articles en vigueur d'un bloc. Le texte source entier
    n'est téléchargé qu'une fois par (fonds, legifrance_source_id) (cache),
    même si plusieurs blocs y font référence — voir _fetch_text(). `fonds`
    par défaut "LEGI" (Codes) : tous les appelants actuels de cette fonction
    (blocs_formes_juridiques.py) portent sur des Codes.
    """
    if not legifrance_source_id or not legifrance_section_id:
        raise LegifranceApiError(
            "legifrance_source_id / legifrance_section_id vide — complète "
            "blocs_formes_juridiques.py avant de lancer la collecte."
        )
    texte = _fetch_text(legifrance_source_id, date=date, fonds=fonds)
    section = _find_section(texte, legifrance_section_id)
    if section is None:
        raise LegifranceApiError(
            f"Section '{legifrance_section_id}' introuvable dans le texte '{legifrance_source_id}'."
        )
    return _collect_articles(section)


def fetch_article_by_id(legiarti_id: str, *, date: str | None = None) -> dict:
    """Récupère UN article précis via `consult/getArticle`, par son identifiant
    LEGIARTI — endpoint distinct de `fetch_articles_in_block()` ci-dessus.

    Nécessaire pour le RGPD (bloc `articles_rgpd.py`) : les articles utiles de
    la Loi n°78-17 (30, 36, 37) ne sont PAS regroupés dans une même section
    contiguë de l'arborescence légale (contrairement à SAS/SASU dans le Code
    de commerce) — même situation que les articles CGI de la micro-entreprise,
    déjà identifiée comme cas à part dans blocs_formes_juridiques.py. Plutôt
    que de forcer un identifiant de section qui n'existe pas, on récupère ces
    articles un par un par leur LEGIARTI.

    `id` renvoyé par `consult/getArticle` VÉRIFIÉ documentairement (voir
    docstring du module) mais PAS ENCORE testé par un vrai appel — contrairement
    à `consult/legiPart`, validé le 10/09/2026. La forme de la réponse
    (`payload["article"]` avec les mêmes champs `content`/`num`/`etat`/
    `dateDebut` que dans `consult/legiPart`) est une hypothèse basée sur le
    schéma officiel PISTE, à confirmer au premier appel réel une fois le
    compte PISTE débloqué — voir TODO dans articles_rgpd.py.
    """
    payload = _post("consult/getArticle", {"id": legiarti_id})
    article = payload.get("article", payload)
    if article.get("etat") not in (None, "VIGUEUR"):
        raise LegifranceApiError(
            f"Article '{legiarti_id}' n'est pas en vigueur (etat={article.get('etat')}) — "
            "à vérifier manuellement, ne devrait pas arriver pour un article cité par la CNIL."
        )
    return {
        "article_numero": article.get("num"),
        "texte_brut": strip_html(article.get("content") or ""),
        "date_effet": _parse_legifrance_date(article.get("dateDebut")),
    }


def fetch_articles_by_ids(legiarti_ids: list[str], *, date: str | None = None) -> list[dict]:
    """Enchaîne fetch_article_by_id() pour une liste d'identifiants — un appel
    réseau par article (pas de mise en cache de texte entier possible ici,
    contrairement à fetch_articles_in_block(), puisqu'il n'y a pas de texte
    source commun à télécharger une fois)."""
    return [fetch_article_by_id(legiarti_id, date=date) for legiarti_id in legiarti_ids]


def fetch_articles_in_text(legifrance_source_id: str, *, date: str | None = None, fonds: str = "LEGI") -> list[dict]:
    """Récupère TOUS les articles en vigueur d'un texte entier, sans viser une
    section précise — variante de fetch_articles_in_block() qui saute l'étape
    _find_section() et collecte directement depuis la racine du texte renvoyé
    par _fetch_text().

    Cas d'usage : une source où on veut "tout ce qui est utile au copilot",
    pas un périmètre pré-découpé par bloc (contrairement au Code de commerce,
    où seuls 2-3 chapitres sur des dizaines concernent Wink) — la Loi n°78-17
    est un texte de taille bien plus réduite et entièrement centré sur la
    protection des données, donc le collecter en entier est raisonnable, pas
    un abus du même ordre que collecter tout le Code de commerce (51 Mo,
    7334 articles, vu lors du test du 10/09/2026 avec un textId sans section).

    `fonds` : "LEGI" (défaut, Codes) ou "LODA" (Lois/Ordonnances/Décrets/
    Arrêtés) — la Loi n°78-17 est du fonds LODA, voir texte_loi_rgpd.py et le
    correctif du 17/09/2026 dans _fetch_text().
    """
    texte = _fetch_text(legifrance_source_id, date=date, fonds=fonds)
    return _collect_articles(texte)
