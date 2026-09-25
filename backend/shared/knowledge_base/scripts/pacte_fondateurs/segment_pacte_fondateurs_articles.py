"""Segmentation structurelle (Phase 1, sous-étape 1a), service 1.1.13 pacte de
fondateurs (Groupe 5). Lit la sortie de `extract_pacte_fondateurs_raw.py`
(paragraphes bruts) et la découpe en segments, SANS ENCORE décider quelle
hiérarchie (article / variante / sous-variante) chaque segment représente.

Lancement, depuis `wink/` :

    python -m backend.shared.knowledge_base.scripts.pacte_fondateurs.segment_pacte_fondateurs_articles \
        --label modele_principal

    python -m backend.shared.knowledge_base.scripts.pacte_fondateurs.segment_pacte_fondateurs_articles \
        --label notice_explicative

Lit `data/pacte_fondateurs/raw_<label>.json`, écrit
`data/pacte_fondateurs/segmented_<label>.json`.

RÈGLE DE DÉCOUPAGE — purement mécanique, sur 2 marqueurs visibles dans le texte
Word lui-même, aucun jugement sémantique :
1. Un paragraphe qui commence par `Article <numéro>` (regex sur le numéro
   uniquement — le séparateur qui suit varie dans le fichier source : "-", "–",
   ":", ".", tabulation... voir `_ARTICLE_RE`).
2. Un paragraphe qui commence par `*` — ce sont les instructions du modèle
   Bpifrance à la personne qui le remplit à la main (ex. "*Hypothèse 2 : ...",
   "*En cas de droit de préemption portant sur la totalité..."), annonçant
   qu'un bloc de texte alternatif suit.

POURQUOI ne pas regrouper directement par hiérarchie (article > variante >
sous-variante) ICI : l'inspection du brut (voir Article 3, qui contient 7
`*Hypothèse` ET, À L'INTÉRIEUR de chacune, des `*En cas de...` supplémentaires)
montre une imbrication à au moins 2 niveaux, pas uniforme d'un article à
l'autre. Décider quel niveau chaque `*` représente sans confirmation externe,
c'est exactement le pas qui a produit le JSON incohérent la première fois
(voir échange du 20/09/2026 avec l'utilisateur). Ce script s'arrête donc à une
liste PLATE de segments, dans l'ordre du document — la hiérarchie se décide
en relisant ce résultat, à l'étape suivante (1b), pas ici.
"""
import argparse
import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data" / "pacte_fondateurs"
_ARTICLE_RE = re.compile(r"^Article\s+(\d+)")


def _is_annotation(texte: str) -> bool:
    return texte.strip().startswith("*")


def segment_paragraphs(paragraphes: list[dict]) -> list[dict]:
    segments: list[dict] = []
    current: dict | None = None

    for p in paragraphes:
        texte = p["texte"]
        stripped = texte.strip()
        article_match = _ARTICLE_RE.match(stripped)
        is_annotation = _is_annotation(texte)

        if article_match or is_annotation:
            if current is not None:
                segments.append(current)
            current = {
                "type": "titre_article" if article_match else "annotation",
                "article_numero": int(article_match.group(1)) if article_match else None,
                "paragraphes": [p],
            }
        else:
            if current is None:
                # Texte avant tout marqueur (ex. préambule, formule d'entrée) —
                # segment "hors marqueur", pas une erreur.
                current = {"type": "hors_marqueur", "article_numero": None, "paragraphes": []}
            current["paragraphes"].append(p)

    if current is not None:
        segments.append(current)

    return segments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Doit correspondre à un raw_<label>.json déjà extrait.")
    args = parser.parse_args()

    inpath = _DATA_DIR / f"raw_{args.label}.json"
    with open(inpath, encoding="utf-8") as f:
        raw = json.load(f)

    segments = segment_paragraphs(raw["paragraphes"])

    outpath = _DATA_DIR / f"segmented_{args.label}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"source_file": args.label, "segments": segments}, f, ensure_ascii=False, indent=2)

    par_type = {}
    for s in segments:
        par_type[s["type"]] = par_type.get(s["type"], 0) + 1
    print(f"OK — {len(segments)} segment(s) -> {outpath}")
    print(f"   dont : {par_type}")


if __name__ == "__main__":
    main()
