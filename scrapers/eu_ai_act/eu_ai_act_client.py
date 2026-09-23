"""Client EUR-Lex pour l'AI Act — communique en HTTP simple (pas d'auth, page
HTML publique), rien d'autre (aucune notion de legal_texts, aucun LLM) — meme
separation que legifrance_client.py.

Ce qui est VERIFIE par une vraie requete (test du 19/09/2026, sur
texte_ai_act.py::TEXTES_AI_ACT[0]) :
- la page renvoie un bloc HTML par article : `<div class="eli-subdivision"
  id="art_N">` (N = numero, ex: "art_5", ou "art_4a" pour un article insere
  par amendement type "Article 4 bis") — 119 blocs trouves sur la version
  consolidee au 27/07/2026 (113 articles de base + quelques articles
  inseres/renumerotes par amendement).
- le numero et le titre de l'article sont dans des balises dediees a
  l'interieur du bloc : `<p class="title-article-norm">Article N</p>` et
  `<div class="eli-title"><p class="stitle-article-norm">Titre</p></div>` —
  extraits separement puis retires avant de recuperer le corps, pour ne pas
  les dupliquer dans texte_brut.
- aucune imbrication d'un bloc eli-subdivision dans un autre a l'interieur
  d'un article (verifie par comptage sur les 119 blocs) — pas de risque de
  capturer un article dans un autre.
- les annexes (id commencant par "anx_") et les chapitres/sections englobants
  (id type "cpt_...", "sct_...") ne matchent pas le pattern `^art_\\d+[a-zA-Z]*$`
  utilise ici — seuls les articles proprement dits sont extraits, HORS
  PERIMETRE volontaire des annexes (a traiter separement si un besoin
  confirme apparait, ex: Annexe III listant les cas d'usage a haut risque).

Ce qui N'EST PAS verifie :
- la stabilite de cette structure HTML dans le temps : EUR-Lex peut changer
  son balisage sans preavis (contrairement a l'API PISTE, versionnee). Si
  fetch_articles_in_text() renvoie soudainement 0 article (ou une
  EurLexClientError), verifier ici en premier la structure reelle de la page.
"""
import re
import unicodedata

import requests
from bs4 import BeautifulSoup

_ARTICLE_ID_RE = re.compile(r"^art_\d+[a-zA-Z]*$")


class EurLexClientError(Exception):
    """Échec de récupération ou de parsing de la page EUR-Lex."""


def _normaliser_texte(texte: str) -> str:
    texte = unicodedata.normalize("NFKC", texte).replace("\xa0", " ")
    return re.sub(r"\s+", " ", texte).strip()


def _normaliser_numero(texte_brut_numero: str) -> str:
    """"Article 5" -> "5", "Article 4 bis" -> "4 bis"."""
    texte = _normaliser_texte(texte_brut_numero)
    return re.sub(r"^Article\s*", "", texte, flags=re.IGNORECASE).strip()


def _extraire_articles(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[dict] = []
    for div in soup.find_all("div", class_="eli-subdivision", id=_ARTICLE_ID_RE):
        numero_tag = div.find("p", class_="title-article-norm")
        numero = _normaliser_numero(numero_tag.get_text(separator=" ")) if numero_tag else div.get("id")
        if numero_tag is not None:
            numero_tag.decompose()

        titre = ""
        titre_div = div.find("div", class_="eli-title")
        if titre_div is not None:
            titre_p = titre_div.find("p", class_="stitle-article-norm")
            if titre_p is not None:
                titre = _normaliser_texte(titre_p.get_text(separator=" "))
            titre_div.decompose()

        corps = _normaliser_texte(div.get_text(separator=" "))
        texte_brut = f"{titre}\n\n{corps}" if titre else corps
        articles.append({"article_numero": numero, "texte_brut": texte_brut})
    return articles


def fetch_articles_in_text(source_url: str, *, timeout: int = 60) -> list[dict]:
    """Récupère et découpe en articles la page EUR-Lex à `source_url` — un seul
    appel HTTP, tout le découpage se fait localement (voir docstring module :
    pas d'endpoint par article comme Légifrance)."""
    try:
        response = requests.get(source_url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    except requests.RequestException as exc:
        raise EurLexClientError(f"Échec de la requête vers {source_url} : {exc}") from exc
    if response.status_code != 200:
        raise EurLexClientError(f"Échec HTTP {response.status_code} sur {source_url}")

    articles = _extraire_articles(response.text)
    if not articles:
        raise EurLexClientError(
            f"Aucun article trouvé sur {source_url} — la structure HTML d'EUR-Lex a peut-être changé, "
            "voir docstring du module."
        )
    return articles
