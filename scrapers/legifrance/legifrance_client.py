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
- 25/09/2026 (service 1.1.13, categorie 3 -- agent conversationnel pacte de
  fondateurs) : `fetch_single_article_by_id()` ci-dessous appelle
  `consult/getArticle {"id": ...}`, endpoint documente publiquement (voir
  module docstring plus haut) mais JAMAIS appele reellement depuis ce repo --
  seul `consult/legiPart` (fetch_articles_in_block) l'a ete. La forme exacte
  de la reponse (champ "texte" vs "content", presence ou non d'un wrapper
  "article": {...}) est donc une hypothese, pas un fait verifie. La fonction
  cherche plusieurs noms de champs possibles et LEVE UNE ERREUR EXPLICITE
  listant les cles reellement recues si aucun ne correspond, plutot que de
  deviner silencieusement -- a corriger au vu de la vraie reponse au premier
  lancement reel (voir collect_legal_texts_pacte_fondateurs.py).
"""
import os
import re
import time
from datetime import date as date_type, datetime, timedelta, timezone
from html import unescape

import requests

_TOKEN_URL = "https://oauth.piste.gouv.fr/api/oauth/token"
_API_BASE = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"

_token: str | None = None
_token_expires_at: float = 0.0

# Cache en mémoire process du texte entier par legifrance_source_id — évite de
# retélécharger 51 Mo à chaque bloc quand plusieurs blocs partagent le même
# texte source (9 blocs pour le seul Code de commerce, voir docstring module).
_text_cache: dict[str, dict] = {}


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


def _fetch_text(legifrance_source_id: str, *, date: str | None = None) -> dict:
    """Récupère le texte entier (code/loi) via consult/legiPart, mis en cache
    par legifrance_source_id — voir docstring du module : un identifiant de
    section n'est pas accepté en entrée, seul le texte entier l'est.

    `date` par défaut = aujourd'hui, jamais omis : un premier essai sans date
    a échoué avec une erreur 500 côté serveur PISTE (message générique,
    "exception non gérée") sur le Code de commerce — le schéma officiel de
    consult/legiPart prévoit ce champ, et on veut de toute façon la version en
    vigueur aujourd'hui (cohérent avec le filtre etat="VIGUEUR" plus bas).
    """
    if legifrance_source_id in _text_cache:
        return _text_cache[legifrance_source_id]

    body = {"textId": legifrance_source_id, "date": date or date_type.today().isoformat()}
    payload = _post("consult/legiPart", body)
    _text_cache[legifrance_source_id] = payload
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


def _parse_legifrance_date(value) -> date_type | None:
    """Légifrance renvoie ses dates en millisecondes depuis 1970 (ex: dateDebut
    = 969494400000), pas en texte lisible — vu en pratique sur un vrai appel
    (erreur `cannot cast type bigint to date` avant cette conversion). Gère
    aussi une chaîne ISO par prudence, au cas où un autre champ l'utilise.

    BUG REEL corrige le 25/09/2026 (service 1.1.13, categorie 3 -- constate
    sur un vrai run Windows, `OSError: [Errno 22] Invalid argument`) :
    `datetime.fromtimestamp()` s'appuie sur les fonctions C de la libc/CRT de
    l'OS pour convertir un timestamp -- sous Windows, cette conversion ECHOUE
    pour un timestamp NEGATIF (date avant le 01/01/1970), alors qu'elle
    fonctionne sous Linux. Des articles anciens (ex: art. 1591 et 1843-4 du
    Code civil, Code Napoleon 1804) ont un `dateDebut` largement anterieur a
    1970 -- jamais rencontre par le pipeline forme_juridique (Code de
    commerce, articles plus recents), donc bug latent jamais declenche avant.
    Corrige en calculant la date par ARITHMETIQUE PURE (timedelta depuis
    l'epoque), qui n'appelle aucune fonction C dependante de l'OS -- comporte-
    ment identique sur toutes les plateformes.
    """
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    if isinstance(value, (int, float)):
        return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=value)).date()
    if isinstance(value, str):
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
    legifrance_source_id: str, legifrance_section_id: str, *, date: str | None = None
) -> list[dict]:
    """Récupère tous les articles en vigueur d'un bloc. Le texte source entier
    n'est téléchargé qu'une fois par legifrance_source_id (cache), même si
    plusieurs blocs y font référence — voir _fetch_text().
    """
    if not legifrance_source_id or not legifrance_section_id:
        raise LegifranceApiError(
            "legifrance_source_id / legifrance_section_id vide — complète "
            "blocs_formes_juridiques.py avant de lancer la collecte."
        )
    texte = _fetch_text(legifrance_source_id, date=date)
    section = _find_section(texte, legifrance_section_id)
    if section is None:
        raise LegifranceApiError(
            f"Section '{legifrance_section_id}' introuvable dans le texte '{legifrance_source_id}'."
        )
    return _collect_articles(section)


def fetch_single_article_by_id(legifrance_article_id: str, *, date: str | None = None) -> dict:
    """Recupere UN article precis par son identifiant LEGIARTI, via
    `consult/getArticle` -- endpoint DIFFERENT de `fetch_articles_in_block()`
    (qui exige de connaitre une section LEGISCTA entiere). Utile quand on
    connait deja l'article exact vise (ex: un article de loi cite dans
    `clause_validity_criteria`) et qu'on ne veut pas parcourir toute une
    section pour l'y retrouver.

    Voir docstring du module : endpoint documente mais PAS ENCORE VERIFIE par
    un vrai appel -- la forme de la reponse est une hypothese. `date` n'est
    pas documente comme parametre de getArticle (contrairement a legiPart) ;
    laisse en option ici par coherence d'API avec fetch_articles_in_block,
    mais non envoye dans le corps de la requete tant que non confirme utile.
    """
    payload = _post("consult/getArticle", {"id": legifrance_article_id})

    article = payload.get("article", payload)  # wrapper "article" hypothetique -- voir docstring module

    texte_html = article.get("texte") or article.get("content")
    if texte_html is None:
        raise LegifranceApiError(
            "Reponse de consult/getArticle sans champ 'texte' ni 'content' -- "
            f"forme de reponse non anticipee (cles recues : {sorted(payload.keys())}, "
            f"cles de 'article' : {sorted(article.keys()) if isinstance(article, dict) else 'N/A'}). "
            "Voir docstring du module : cet endpoint n'a jamais ete verifie par un vrai appel, "
            "ajuster ce parsing au vu de la vraie reponse plutot que de deviner."
        )

    etat = article.get("etat")
    if etat is not None and etat != "VIGUEUR":
        raise LegifranceApiError(
            f"Article '{legifrance_article_id}' n'est pas en vigueur (etat={etat!r}) -- "
            "non collecte (meme regle que fetch_articles_in_block, voir _collect_articles)."
        )

    return {
        "article_numero": article.get("num"),
        "texte_brut": strip_html(texte_html),
        "date_effet": _parse_legifrance_date(article.get("dateDebut")),
    }
