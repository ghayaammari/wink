"""Collecte du référentiel des journaux habilités (JAL / SPEL) depuis le
registre national actulegales.fr (APTE) — service 1.1.5.

Pourquoi cette source : Service-Public (fiche R44934 « Rechercher un support
habilité par département ») renvoie vers ce registre. Une seule source
structurée au lieu des ~100 arrêtés préfectoraux annuels (PDF hétérogènes).

Structure observée le 25/09/2026 (via lecteur web, pas d'accès au HTML brut
depuis l'environnement de dev — parseur à VÉRIFIER au premier lancement) :
- pages de liste A→Z : https://actulegales.fr/journaux-annonces-legales/{a..z,-}
- une ligne par journal : lien vers sa fiche
  (https://annonces-legales.actulegales.fr/<slug>) + « Département(s) : Ain, … »
Le parseur est volontairement tolérant (cherche les liens de fiche, puis le
texte « Département(s) : » dans la ligne qui les contient) et le script
appelant échoue bruyamment si une page ne donne aucun journal.

Ce module ne parle QU'À la source (récupération + parsing) : aucune notion de
base de données ni de code département (fait par le script de collecte).
"""
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scrapers.shared.web_fetch import fetch_page

URL_LISTE = "https://actulegales.fr/journaux-annonces-legales/{lettre}"
LETTRES = [*"abcdefghijklmnopqrstuvwxyz", "-"]
_DOMAINE_FICHE = "annonces-legales.actulegales.fr"
# Un nom qui est un nom de domaine (« aisnenouvelle.fr ») = service de presse en ligne.
_RE_NOM_DOMAINE = re.compile(r"^[\w.-]+\.(fr|com|net|org|info|eu|re|nc|pf|gp|mq|yt|gf)$", re.IGNORECASE)


class ActulegalesError(Exception):
    """Page de liste inaccessible ou structure non reconnue."""


@dataclass(frozen=True)
class JournalBrut:
    nom: str
    type_support: str  # 'papier' | 'spel' (heuristique, corrigeable à la validation)
    departements_noms: list[str]
    lien_fiche: str


def _nettoyer_nom(nom: str) -> str:
    nom = " ".join(nom.split())
    return re.sub(r"\b([LlDd])['’]\s+", r"\1'", nom)  # « L' Ain Agricole » -> « L'Ain Agricole »


def _type_support(nom: str) -> str:
    return "spel" if _RE_NOM_DOMAINE.match(nom.replace(" ", "")) else "papier"


def parser_page_liste(html: str, url_page: str) -> list[JournalBrut]:
    """Fonction pure : HTML d'une page de liste -> journaux (sans doublon)."""
    soup = BeautifulSoup(html, "lxml")
    journaux: list[JournalBrut] = []
    vus: set[str] = set()
    for lien in soup.find_all("a", href=True):
        href = urljoin(url_page, lien["href"]).split("#")[0]
        if urlparse(href).netloc != _DOMAINE_FICHE or href in vus:
            continue
        nom = _nettoyer_nom(lien.get_text(" ", strip=True))
        if not nom:
            continue
        ligne = lien.find_parent("tr") or lien.find_parent("li") or lien.parent
        texte = " ".join(ligne.get_text(" ", strip=True).split()) if ligne else ""
        m = re.search(r"D[ée]partements?\s*(?:\(s\))?\s*:\s*(.+)$", texte)
        noms = [n.strip(" .") for n in re.split(r",|;|\s+et\s+", m.group(1))] if m else []
        vus.add(href)
        journaux.append(
            JournalBrut(nom=nom, type_support=_type_support(nom), departements_noms=[n for n in noms if n], lien_fiche=href)
        )
    return journaux


def recuperer_journaux(lettre: str) -> list[JournalBrut]:
    url = URL_LISTE.format(lettre=lettre)
    page = fetch_page(url)
    if page is None or not page.html_brut:
        raise ActulegalesError(f"Page {url} inaccessible (robots.txt, réseau ou contenu vide).")
    return parser_page_liste(page.html_brut, url)
