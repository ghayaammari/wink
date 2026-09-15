"""Recuperation de pages web generique, source-agnostique — aucune notion
d'assurance ni de secteur ici (SRP). Reutilisable par n'importe quel futur
scraper base sur du HTML public (pas seulement le volet assurance).

Garde-fous respectes vis-a-vis des serveurs distants, absents du reste du
depot avant ce fichier :
  - `robots.txt` verifie avant toute recuperation (`is_allowed_by_robots`).
  - Rate-limiting par domaine (`_respect_rate_limit`) — jamais deux requetes
    vers le meme domaine en moins de `_MIN_DELAY_SECONDS`.
  - `User-Agent` identifiant, jamais l'UA par defaut de `requests`.
  - `fetch_page()` ne leve jamais d'exception reseau : renvoie `None` sur
    tout echec (bloque par robots.txt, timeout, 404, PDF illisible...) pour
    que l'orchestrateur appelant puisse simplement passer a la page suivante
    plutot que d'interrompre toute la collecte.

Cache memoire uniquement (process courant, pas de persistance disque) — meme
choix que `_text_cache` dans `scrapers/legifrance/legifrance_client.py`, le
volume de pages ici (quelques dizaines) ne justifie pas plus.
"""
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
import trafilatura
from bs4 import BeautifulSoup
from pypdf import PdfReader
import io

_USER_AGENT = "Wink-Copilot-Bot/1.0 (+contact: ghayaammari19@gmail.com; usage: collecte ponctuelle de guides assurance startup, volume borne)"
_REQUEST_TIMEOUT_SECONDS = 15
_MIN_DELAY_SECONDS = 2.0

_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser] = {}
_LAST_FETCH_AT: dict[str, float] = {}
_PAGE_CACHE: dict[str, "FetchedPage | None"] = {}


@dataclass(frozen=True)
class FetchedPage:
    url: str
    titre: str
    texte_extrait: str
    html_brut: str  # vide pour un PDF — pas de graphe de liens a en extraire


def _domain(url: str) -> str:
    return urlparse(url).netloc


def is_allowed_by_robots(url: str) -> bool:
    """Verifie robots.txt du domaine de `url` pour notre User-Agent.

    Le robots.txt est recupere via `requests` (avec notre `_USER_AGENT`),
    jamais via `RobotFileParser.read()` : celui-ci utilise `urllib.request`
    en interne, qui envoie un User-Agent generique — plusieurs sites
    institutionnels le bloquent (403, pare-feu anti-bot) alors qu'ils
    acceptent un User-Agent identifiant comme le notre. Un 403 sur ce fetch
    interne ferait alors interpreter (a tort) tout le site comme interdit.

    Si robots.txt est absent (404) ou inaccessible pour une autre raison que
    401/403, on considere l'acces autorise (comportement standard : un site
    sans robots.txt n'interdit rien par defaut)."""
    domain = _domain(url)
    parser = _ROBOTS_CACHE.get(domain)
    if parser is None:
        parser = urllib.robotparser.RobotFileParser()
        robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
        try:
            response = requests.get(
                robots_url, headers={"User-Agent": _USER_AGENT}, timeout=_REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code in (401, 403):
                parser.disallow_all = True
            elif response.status_code >= 400:
                parser.allow_all = True  # pas de robots.txt -> rien d'interdit
            else:
                parser.parse(response.text.splitlines())
        except requests.RequestException:
            parser.allow_all = True  # inaccessible -> pas de restriction connue
        _ROBOTS_CACHE[domain] = parser
    return parser.can_fetch(_USER_AGENT, url)


def _respect_rate_limit(domain: str) -> None:
    last_fetch = _LAST_FETCH_AT.get(domain)
    if last_fetch is not None:
        elapsed = time.time() - last_fetch
        if elapsed < _MIN_DELAY_SECONDS:
            time.sleep(_MIN_DELAY_SECONDS - elapsed)
    _LAST_FETCH_AT[domain] = time.time()


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


def fetch_page(url: str) -> FetchedPage | None:
    """Point d'entree public. Ne leve jamais — renvoie None sur tout echec."""
    if url in _PAGE_CACHE:
        return _PAGE_CACHE[url]

    if not is_allowed_by_robots(url):
        _PAGE_CACHE[url] = None
        return None

    domain = _domain(url)
    _respect_rate_limit(domain)

    try:
        response = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        _PAGE_CACHE[url] = None
        return None

    # `requests` retombe sur ISO-8859-1 par defaut quand le Content-Type ne
    # precise pas de charset (defaut HTTP/1.1) — quasi toujours faux pour les
    # sites francais modernes en UTF-8 sans charset explicite dans l'en-tete,
    # ce qui corrompait les caracteres accentues (mojibake). `apparent_encoding`
    # detecte le charset depuis le contenu reel (chardet/charset-normalizer),
    # bien plus fiable ici.
    response.encoding = response.apparent_encoding

    content_type = response.headers.get("Content-Type", "")
    is_pdf = "application/pdf" in content_type or url.lower().endswith(".pdf")

    if is_pdf:
        try:
            texte = _extract_pdf_text(response.content)
        except Exception:
            _PAGE_CACHE[url] = None
            return None
        if not texte:
            _PAGE_CACHE[url] = None
            return None
        page = FetchedPage(url=url, titre=url.rsplit("/", 1)[-1], texte_extrait=texte, html_brut="")
        _PAGE_CACHE[url] = page
        return page

    html_brut = response.text
    texte_extrait = trafilatura.extract(html_brut, url=url, favor_precision=True)
    if not texte_extrait:
        _PAGE_CACHE[url] = None
        return None

    metadata = trafilatura.extract_metadata(html_brut)
    titre = (metadata.title if metadata and metadata.title else url)

    page = FetchedPage(url=url, titre=titre, texte_extrait=texte_extrait, html_brut=html_brut)
    _PAGE_CACHE[url] = page
    return page


def discover_links(html_brut: str, base_url: str, max_links: int) -> list[str]:
    """Extrait les liens internes (meme domaine que `base_url`) d'une page
    deja recuperee — jamais d'appel reseau ici. Plafonne a `max_links`."""
    if not html_brut or max_links <= 0:
        return []

    base_domain = _domain(base_url)
    soup = BeautifulSoup(html_brut, "lxml")
    seen: set[str] = set()
    links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        absolute = urljoin(base_url, anchor["href"]).split("#")[0]
        if not absolute.startswith("http"):
            continue
        if _domain(absolute) != base_domain:
            continue
        if absolute in seen or absolute == base_url:
            continue
        seen.add(absolute)
        links.append(absolute)
        if len(links) >= max_links:
            break

    return links
