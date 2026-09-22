"""Client de collecte des pages de l'encyclopedie Bpifrance Creation --
nouvelle source (25/09/2026, service 1.1.13 categorie 3), dossier separe de
`scrapers/legifrance/` et `scrapers/judilibre/` par la meme convention
("scrapers/ organise par source") : ni une API officielle avec cle, ni du
droit code, juste des pages HTML publiques du meme editeur institutionnel
que le modele de pacte deja utilise (coherence de ton avec le contenu deja
en base, voir echange avec l'utilisateur sur les ressources).

PAS d'API ici (aucune n'est publiee par Bpifrance Creation pour son
encyclopedie) : un simple GET + parsing HTML (BeautifulSoup, deja une
dependance du repo -- voir requirements.txt, discover_links). Pas de
nouvelle dependance ajoutee (html2text notamment, absent du repo) --
`get_text()` de BeautifulSoup suffit pour ce besoin (extraction de
paragraphes, pas de mise en forme riche a preserver).

A verifier avant usage en production (pas fait ici, pas d'acces reseau
sortant depuis ce script au moment de l'ecriture) : les CGU du site
(bpifrance-creation.fr) autorisant explicitement ce type de collecte
automatisee -- voir echange avec l'utilisateur, distinct du cas Legifrance/
Judilibre (Licence Ouverte explicite pour les donnees publiques de l'Etat,
pas necessairement le cas d'un site d'encyclopedie edite par un etablissement
public a caractere different).
"""
import re

import requests
from bs4 import BeautifulSoup

_TIMEOUT_SECONDES = 15
_USER_AGENT = "Wink-KnowledgeBase-Collecte/1.0 (contact via l'equipe produit Wink)"


class BpifranceEncyclopedieError(Exception):
    """Echec de recuperation ou de parsing d'une page de l'encyclopedie."""


def fetch_page_text(url: str) -> str:
    """Recupere une page et retourne son texte principal, nettoye.

    Ne tente PAS de deviner la structure precise de la page (pas de
    selecteur CSS specifique au thème Bpifrance, fragile a un changement de
    site) : prend le texte de <article> ou <main> si present, sinon <body>
    entier -- puis retire scripts/styles/nav/header/footer avant extraction,
    seule heuristique appliquee. Un contenu manifestement incomplet (moins de
    200 caracteres) leve une erreur explicite plutot que d'inserer une page
    d'erreur/cookie-banner comme si c'etait du contenu reel.
    """
    try:
        response = requests.get(
            url, timeout=_TIMEOUT_SECONDES, headers={"User-Agent": _USER_AGENT}
        )
    except requests.RequestException as exc:
        raise BpifranceEncyclopedieError(f"Echec de recuperation de '{url}' : {exc}") from exc

    if response.status_code != 200:
        raise BpifranceEncyclopedieError(f"'{url}' a repondu {response.status_code}.")

    soup = BeautifulSoup(response.text, "lxml")
    for balise in soup.select("script, style, nav, header, footer"):
        balise.decompose()

    contenu = soup.select_one("article") or soup.select_one("main") or soup.body
    if contenu is None:
        raise BpifranceEncyclopedieError(f"'{url}' : aucun contenu HTML exploitable trouve.")

    texte = contenu.get_text(separator="\n")
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r"\n\s*\n+", "\n\n", texte).strip()

    if len(texte) < 200:
        raise BpifranceEncyclopedieError(
            f"'{url}' : texte extrait trop court ({len(texte)} caracteres) -- "
            "probable page d'erreur ou bandeau cookies plutot que le vrai contenu, "
            "a verifier manuellement avant de relancer."
        )
    return texte
