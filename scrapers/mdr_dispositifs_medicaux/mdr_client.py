"""Client EUR-Lex pour le MDR (règlement UE 2017/745, dispositifs médicaux) —
communique en HTTP simple (pas d'auth, page HTML publique), rien d'autre
(aucune notion de legal_texts, aucun LLM) — même séparation que
legifrance_client.py.

DUPLIQUÉ depuis scrapers/eu_ai_act/eu_ai_act_client.py plutôt que factorisé
dans un client EUR-Lex partagé — décision explicite (19/09/2026) : la logique
de parsing est identique (même moteur EUR-Lex, même structure `eli-subdivision`
par article), mais factoriser maintenant reviendrait à toucher le scraper
AI Act déjà validé en production pour un bénéfice qui ne se justifie qu'à
partir d'un 3ème texte EUR-Lex. Dette technique assumée et documentée : si un
3ème texte EUR-Lex apparaît, factoriser à ce moment-là dans scrapers/shared/
plutôt que dupliquer une 3ème fois.

Contrairement à eu_ai_act_client.py, la structure HTML ci-dessous n'a PAS
encore été vérifiée par un vrai appel sur la page MDR (CELEX 32017R0745) au
moment de l'écriture (19/09/2026) — seule l'hypothèse que EUR-Lex utilise le
même moteur de rendu HTML pour tous ses textes consolidés (vérifié pour l'AI
Act) justifie de réutiliser ce parsing tel quel. Si fetch_articles_in_text()
renvoie 0 article sur la page MDR, vérifier ici en premier la structure réelle
de la page (peut différer légèrement d'un règlement à l'autre).
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
