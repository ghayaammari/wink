"""Extraction des variables (Phase 1, sous-étape 1b), service 1.1.4 statuts SAS.
Lit la sortie de `segment_statuts_sas_articles.py` (segments plats, Phase 1a)
et repère, pour CHAQUE OCCURRENCE d'un placeholder dans le texte source, un
type de variable candidat — même rôle que
`extract_pacte_fondateurs_variables.py` (1.1.13), adapté à la syntaxe de
placeholder de CE modèle (Bpifrance statuts, différente du pacte).

Lancement, depuis `wink/` :

    python -m backend.shared.knowledge_base.scripts.extract_statuts_sas_variables \
        --label modele_sas

Lit `data/statuts_sas_raw/segmented_<label>.json`, écrit
`data/statuts_sas_raw/variables_<label>.json`.

SYNTAXE DE PLACEHOLDER — différente du pacte, vérifiée sur le texte réel
(22/09/2026) : le modèle pacte utilise `(libellé)` seul ; CE modèle utilise
`.....(libellé)` — des points de suspension COLLÉS à la parenthèse ouvrante
(ex. "né(e) le .....(date de naissance)"). Un `(...)` SANS ces points qui le
précède n'est quasiment jamais un vrai placeholder ici (vérifié : sur 244
parenthèses trouvées dans le document, 192 sont précédées de `...` — un vrai
placeholder à remplir — et les 52 restantes sont des usages grammaticaux
("le(s)", accord), des énumérations ("(i)", "(ii)", "(iii)"), un sigle
("(ESS)"), ou un montant déjà écrit en toutes lettres suivi du chiffre entre
parenthèses ("trois (3) mois", "quatre (4) mois") — AUCUN de ces 52 cas n'est
un blanc à remplir par l'entrepreneur). La regex ne capture donc QUE les
parenthèses précédées de `..` ou plus, contrairement au pacte qui capture
toute parenthèse et exclut ensuite au cas par cas (`NON_VARIABLE`) : ici
l'exclusion se fait en amont, par le marqueur syntaxique lui-même, plus fiable
que de deviner après coup sur 52 cas hétérogènes.

Cas particulier documenté, PAS géré automatiquement ici (laissé A_CONFIRMER) :
"NOMBRE (CHIFFRE euros)" — une instruction de rédaction du modèle lui-même
("écrivez le nombre en toutes lettres, puis son chiffre entre parenthèses"),
pas un placeholder au sens des autres. Elle n'a pas la syntaxe `.....(...)`
donc n'est de toute façon pas capturée par la regex — traçée manuellement en
Phase 1b si une clause qui en dépend est retenue (probablement l'article sur
le capital social).

CLASSIFICATION DU TYPE — règles déterministes, reprises du pacte
(`_DUREE_UNITS`, détection montant/date/nombre_ordinal, tout le reste en
`A_CONFIRMER` plutôt que deviné). Un placeholder qui ne correspond à aucune
règle sûre reçoit `A_CONFIRMER`, avec son contexte — à trancher avec
l'utilisateur en Phase 1b, jamais deviné ici.
"""
import argparse
import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data" / "statuts_sas_raw"
_PLACEHOLDER_RE = re.compile(r"\.{2,}\s*\(([^)]+)\)")
_DUREE_UNITS = (
    "jour", "jours", "mois", "an", "ans", "année", "années",
    "semaine", "semaines", "trimestre", "trimestres", "semestre", "semestres",
)
_AMBIGU_MARKERS = ("indiquer", "préciser", "«")
_INSTRUCTION_MARKERS = (
    "à compléter", "insérer", "notamment", "y compris", "le cas échéant",
    "à l'exception", "à l’exception", "ne doit pas excéder", "pour une ",
    "pour définir", "compte tenu", "…", "décrire",
)
_ORDINAL_PLACEHOLDER_RE = re.compile(r"^x[eè]me$", re.IGNORECASE)


def _slugify(texte: str) -> str:
    s = texte.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def classify(libelle: str, texte_suivant: str) -> str:
    t = libelle.strip()
    tl = t.lower()

    if "/" in t or any(tl.startswith(m) or m in tl for m in _AMBIGU_MARKERS):
        return "A_CONFIRMER"

    if any(marker in tl for marker in _INSTRUCTION_MARKERS):
        return "A_CONFIRMER"

    if len(t.split()) > 5 or " ou " in tl or tl.startswith("ou "):
        return "A_CONFIRMER"

    if _ORDINAL_PLACEHOLDER_RE.match(t) or re.search(r"\brang\b", tl) or re.search(r"\bordinal\b", tl):
        return "nombre_ordinal"

    if re.search(r"\bdate\b", tl):
        return "date"

    if re.search(r"\bmontant\b", tl) or re.search(r"\bcapital\b", tl) or "€" in t or "euro" in tl:
        return "montant"

    if tl == "nombre" or tl == "chiffre":
        suivant = texte_suivant[:20].lower()
        if any(unit in suivant for unit in _DUREE_UNITS):
            return "duree"
        return "nombre"

    return "texte"


def extract_variables(segments: list[dict]) -> list[dict]:
    results = []
    for segment in segments:
        occurrences = []
        for p in segment["paragraphes"]:
            texte = p["texte"]
            for m in _PLACEHOLDER_RE.finditer(texte):
                libelle = m.group(1)
                type_ = classify(libelle, texte[m.end():])
                debut_contexte = max(0, m.start() - 30)
                occurrences.append({
                    "paragraphe_index": p["index"],
                    "libelle": libelle,
                    "nom": _slugify(libelle),
                    "type": type_,
                    "contexte": texte[debut_contexte:m.end() + 30],
                })
        if occurrences:
            results.append({
                "segment_type": segment["type"],
                "article_numero": segment.get("article_numero"),
                "premier_paragraphe_index": segment["paragraphes"][0]["index"],
                "occurrences": occurrences,
            })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Doit correspondre à un segmented_<label>.json déjà produit.")
    args = parser.parse_args()

    inpath = _DATA_DIR / f"segmented_{args.label}.json"
    with open(inpath, encoding="utf-8") as f:
        data = json.load(f)

    results = extract_variables(data["segments"])

    outpath = _DATA_DIR / f"variables_{args.label}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"source_file": args.label, "segments_avec_variables": results}, f, ensure_ascii=False, indent=2)

    par_type: dict[str, int] = {}
    total = 0
    for seg in results:
        for occ in seg["occurrences"]:
            par_type[occ["type"]] = par_type.get(occ["type"], 0) + 1
            total += 1

    print(f"OK — {total} occurrence(s) de placeholder dans {len(results)} segment(s) -> {outpath}")
    print(f"   par type : {par_type}")
    if par_type.get("A_CONFIRMER"):
        print(f"   /!\\ {par_type['A_CONFIRMER']} occurrence(s) A_CONFIRMER — à trancher avant assemblage des clauses.")


if __name__ == "__main__":
    main()
