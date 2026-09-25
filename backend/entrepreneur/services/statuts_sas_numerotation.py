"""Numérotation des statuts SAS au rendu (service 1.1.4, lot B du 24/09/2026).

Les numéros ne sont JAMAIS écrits dans le clausier (garde-fou du générateur,
lot A) : ils dépendent des articles réellement présents, donc des choix de
l'utilisateur (facultatifs cochés, sections non applicables). Seul le rendu
les connaît. Ce module est la source unique de ces numéros, pour :

- les titres d'article du PDF (« Article 3 – Dénomination sociale ») ;
- les sous-titres « § Titre » des clauses (« 6.2. Apports en nature ») ;
- les renvois « visé à l'article X » (`article_cible` = numéro LOGIQUE du
  clausier, traduit ici en numéro AFFICHÉ) ;
- l'en-tête du formulaire (« Article 12 – Président »).

Numéro logique = celui du modèle Bpifrance (`titre_article_22` -> "22"),
stable, utilisé par le clausier. Numéro affiché = rang de l'article parmi
ceux présents (1, 2, 3… sans trou).

Module séparé de statuts_sas_resolvers.py (déjà très long) : une
responsabilité claire, testable sans base de données (fonctions pures sur
les sections, les réponses et les blocs).
"""
import re

from backend.entrepreneur.services.document_renderer_base import _lit
from backend.entrepreneur.services.statuts_sas_resolvers import articles_par_section

PREFIXE_TITRE_ARTICLE = "titre_article_"
# Sous-titre dans le texte d'une clause : ligne commençant par « § ».
_SOUS_TITRE_RE = re.compile(r"(?m)^§ (.+)$")


def _section_visible(reponse: dict | None) -> bool:
    """Une section produit du contenu si elle a une réponse applicable et
    non refusée (clause optionnelle « non », facultatif non coché)."""
    if reponse is None:
        return False
    return reponse.get("applicable", True) is not False and reponse.get("inclus", True) is not False


def numeros_articles(sections, reponses: dict, article_courant: str | None = None) -> dict[str, int]:
    """{numéro logique: numéro affiché} des articles présents, dans l'ordre du
    squelette. `sections` triées par `ordre`. `article_courant` : article de
    la section en cours de saisie, compté comme présent (le formulaire et
    l'aperçu l'affichent déjà).

    Les articles non encore atteints ne sont pas comptés : pendant la saisie,
    seuls les numéros des articles déjà traités sont définitifs -- ce sont
    les seuls affichés à ce moment-là."""
    article_de = articles_par_section(sections)
    presents: list[str] = []
    for section in sections:
        code = section.code_section
        article = article_de.get(code)
        if article is None or not article.isdigit() or code.startswith(PREFIXE_TITRE_ARTICLE):
            continue  # en-tête, clôture (hors article) ou titre lui-même
        if article in presents:
            continue
        if _section_visible(reponses.get(code)) or article == article_courant:
            presents.append(article)
    return {article: rang for rang, article in enumerate(presents, start=1)}


def libelle_article(numero: int | None, titre: str | None) -> str | None:
    if not titre:
        return None
    return f"Article {numero} – {titre}" if numero is not None else titre


def _numeroter_sous_titres(runs: list[dict], prefixe: str, deja_vus: dict[str, int]) -> list[dict]:
    """Remplace chaque ligne « § Titre » des runs littéraux par
    « {prefixe}.{k}. Titre » (en gras). Un titre déjà numéroté dans le même
    article est retiré : cas des blocs répétés par apporteur (« Apports en
    nature » une seule fois, pas une fois par associé)."""
    resultat: list[dict] = []
    for run in runs:
        if run.get("valeur_utilisateur") or "§ " not in run["texte"]:
            resultat.append(run)
            continue
        position = 0
        texte = run["texte"]
        for match in _SOUS_TITRE_RE.finditer(texte):
            if match.start() > position:
                resultat.append(_lit(texte[position:match.start()]))
            titre = match.group(1).strip()
            fin = match.end()
            if titre not in deja_vus:
                deja_vus[titre] = len(deja_vus) + 1
                resultat.append({**_lit(f"{prefixe}.{deja_vus[titre]}. {titre}"), "gras": True})
            elif fin < len(texte) and texte[fin] == "\n":
                fin += 1  # sous-titre répété : retiré avec son retour à la ligne
            position = fin
        if position < len(texte):
            resultat.append(_lit(texte[position:]))
    return resultat


def numeroter_blocs(blocks: list[dict], sections, numeros: dict[str, int]) -> list[dict]:
    """Post-traitement des blocs des statuts (après assemblage) :
    1. titre d'article -> « Article {n} – {titre} » ;
    2. titres de clause/section retirés : ce sont des libellés du
       FORMULAIRE (« Cessions libres », « Président personne physique »…),
       jamais des titres du document -- ils s'imprimaient en double ;
    3. sous-titres « § » numérotés par article.
    Les blocs `placeholder` (section en cours de saisie, aperçu) gardent leur
    titre : il indique ce qui est en train d'être rédigé."""
    article_de = articles_par_section(sections)
    sous_titres_par_article: dict[str, dict[str, int]] = {}
    resultat: list[dict] = []
    for bloc in blocks:
        bloc = dict(bloc)
        code = bloc.get("code_section") or ""
        article = article_de.get(code)
        if code.startswith(PREFIXE_TITRE_ARTICLE):
            bloc["titre"] = libelle_article(numeros.get(code[len(PREFIXE_TITRE_ARTICLE):]), bloc.get("titre"))
        elif bloc.get("type") != "placeholder":
            bloc["titre"] = None
            numero = numeros.get(article or "")
            if numero is not None:
                bloc["runs"] = _numeroter_sous_titres(
                    bloc.get("runs", []), str(numero), sous_titres_par_article.setdefault(article, {})
                )
        resultat.append(bloc)
    return resultat
