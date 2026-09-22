"""Service 1.1.13 -- corpus pedagogique de l'agent conversationnel pacte de
fondateurs (categorie 3, point "donnees embeddees insuffisantes").

Contexte (echange avec l'utilisateur, 25/09/2026) : le corpus embedde
aujourd'hui pour le domaine `pacte_fondateurs` ne contient que `texte_clause`
et `description_clause` des 61 clauses -- rien de comparatif/pedagogique. La
Notice explicative Bpifrance (573 paragraphes, deja extraite en Phase 1 pour
`raw_notice_explicative.json` / `segmented_notice_explicative.json`) n'a ete
minee a l'epoque que pour reperer 3 trous STRUCTURELS du squelette (Article 1,
Preambule, critere prix determinable) -- jamais pour son contenu explicatif.

Ce script isole les paragraphes de la Notice qui n'existent PAS (ou pas sous
une forme quasi identique) dans le modele principal deja seede : ce sont les
seuls candidats a un contenu reellement pedagogique (le reste n'est que la
meme clause juridique repetee, deja couverte par les embeddings existants).

Regle du repo, deja appliquee dans extract_pacte_fondateurs_variables.py :
JAMAIS deviner silencieusement qu'un paragraphe est "pedagogique" -- ce
script ne fait que le tri deterministe modele/hors-modele + un marquage
d'indices lexicaux, PAS une classification IA. Le fichier de sortie est une
liste de CANDIDATS a relire humainement avant tout embedding (meme logique
que `valide_humain` sur legal_texts) -- rien n'est embedde par ce script.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data" / "pacte_fondateurs"
_NOTICE_FILE = _DATA_DIR / "segmented_notice_explicative.json"
_MODELE_FILE = _DATA_DIR / "segmented_modele_principal.json"
_OUT_FILE = _DATA_DIR / "notice_explicative_candidats_pedagogiques.json"

# Indices lexicaux d'un paragraphe a vocation explicative/comparative plutot
# que d'une clause juridique brute -- affine par relecture humaine, pas une
# decision automatique (voir docstring du module).
_MOTS_CLES_PEDAGOGIQUES = (
    "conseil", "recommand", "exemple", "attention", "pratique",
    "il est preferable", "il est conseille", "avantage", "inconvenient",
    "risque", "a titre indicatif", "il convient de", "hypothese",
)

_LONGUEUR_MIN_CANDIDAT = 40  # exclut les fragments trop courts (titres, "et/ou"...)


def _normaliser(texte: str) -> str:
    """Meme technique que le script de detection des 24 clauses dupliquees
    (session precedente) : normalisation NFKD + suppression diacritiques +
    minuscules + ponctuation retiree + espaces reduits -- pour comparer deux
    formulations du meme texte source malgre des variantes de guillemets/
    apostrophes/espaces (deja rencontre 2 fois dans ce service, voir le bug
    d'apostrophes de l'Article 9)."""
    t = unicodedata.normalize("NFKD", texte)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _paragraphes(segments: list[dict]) -> list[dict]:
    """Aplati les segments en une liste de paragraphes, en conservant
    l'article_numero du segment parent (utile pour grouper la sortie)."""
    out = []
    for segment in segments:
        for p in segment.get("paragraphes", []):
            texte = (p.get("texte") or "").strip()
            if not texte:
                continue
            out.append({
                "article_numero": segment.get("article_numero"),
                "index": p.get("index"),
                "style": p.get("style"),
                "texte": texte,
            })
    return out


def _detecter_mots_cles(texte_normalise: str) -> list[str]:
    return [m for m in _MOTS_CLES_PEDAGOGIQUES if _normaliser(m) in texte_normalise]


def main() -> None:
    notice_data = json.loads(_NOTICE_FILE.read_text(encoding="utf-8"))
    modele_data = json.loads(_MODELE_FILE.read_text(encoding="utf-8"))

    paragraphes_notice = _paragraphes(notice_data["segments"])
    paragraphes_modele = _paragraphes(modele_data["segments"])

    # Ensemble normalise du modele -- un paragraphe de la notice "deja dans
    # le modele" si son texte normalise est un sous-ensemble/sur-ensemble
    # tres proche d'un paragraphe du modele (comparaison par inclusion, pas
    # egalite stricte, car la Notice reformule parfois legerement autour
    # d'une meme clause -- ex. numerotation d'article en plus).
    normalises_modele = [_normaliser(p["texte"]) for p in paragraphes_modele]

    candidats = []
    deja_couverts = 0
    for p in paragraphes_notice:
        if len(p["texte"]) < _LONGUEUR_MIN_CANDIDAT:
            continue
        norm = _normaliser(p["texte"])
        trouve_dans_modele = any(
            norm in m or m in norm
            for m in normalises_modele
            if len(m) > 20  # evite les faux positifs sur des fragments courts communs
        )
        if trouve_dans_modele:
            deja_couverts += 1
            continue
        mots_cles = _detecter_mots_cles(norm)
        candidats.append({
            "article_numero": p["article_numero"],
            "index_notice": p["index"],
            "texte": p["texte"],
            "mots_cles_detectes": mots_cles,
            "confiance_pedagogique": "haute" if mots_cles else "a_verifier",
        })

    _OUT_FILE.write_text(
        json.dumps(
            {
                "source": "raw_notice_explicative.json (573 paragraphes) vs segmented_modele_principal.json",
                "methode": "paragraphe absent (par inclusion normalisee) du modele principal deja seede",
                "avertissement": (
                    "Liste de CANDIDATS, pas un corpus valide -- relecture humaine "
                    "obligatoire avant tout embedding, memes garanties que "
                    "legal_texts.statut_contenu='valide_humain'."
                ),
                "stats": {
                    "paragraphes_notice_total": len(paragraphes_notice),
                    "deja_couverts_par_le_modele": deja_couverts,
                    "candidats_hors_modele": len(candidats),
                    "dont_confiance_haute": sum(1 for c in candidats if c["confiance_pedagogique"] == "haute"),
                },
                "candidats": candidats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Paragraphes notice: {len(paragraphes_notice)}")
    print(f"Deja couverts par le modele (ignores): {deja_couverts}")
    print(f"Candidats hors modele ecrits: {len(candidats)} -> {_OUT_FILE}")
    print(f"  dont confiance haute (mot-cle detecte): {sum(1 for c in candidats if c['confiance_pedagogique'] == 'haute')}")


if __name__ == "__main__":
    main()
