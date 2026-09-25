"""Extraction des variables (Phase 1, sous-étape 1b), service 1.1.13 pacte de
fondateurs (Groupe 5). Lit la sortie de `segment_pacte_fondateurs_articles.py`
(segments plats, Phase 1a) et repère, pour CHAQUE OCCURRENCE d'un placeholder
entre parenthèses dans le texte source, un type de variable candidat.

Lancement, depuis `wink/` :

    python -m backend.shared.knowledge_base.scripts.pacte_fondateurs.extract_pacte_fondateurs_variables \
        --label modele_principal

    python -m backend.shared.knowledge_base.scripts.pacte_fondateurs.extract_pacte_fondateurs_variables \
        --label notice_explicative

Lit `data/pacte_fondateurs/segmented_<label>.json`, écrit
`data/pacte_fondateurs/variables_<label>.json`.

RÈGLE — une occurrence par ligne de sortie, PAS de regroupement par clause
encore (les segments de la Phase 1a ne sont pas encore assemblés en clauses
finales — voir `segment_pacte_fondateurs_articles.py`). Le regroupement/
dédoublonnage par clause se fera à l'étape suivante, une fois les frontières
de clause décidées avec l'utilisateur.

CLASSIFICATION DU TYPE — règles déterministes explicites, AUCUNE devinette
silencieuse sur un cas ambigu. Un placeholder qui ne correspond à aucune
règle sûre reçoit `"A_CONFIRMER"`, avec le texte brut du placeholder ET son
contexte (30 caractères avant/après) — à trancher avec l'utilisateur, pas à
deviner. C'est précisément l'inverse de ce qui a produit le JSON incohérent
de la première extraction (l'heuristique `/` qui confondait `choix` et
`reference_croisee`, voir docstring de `document_generation_service.py`) :
ici, tout placeholder contenant `/`, ou commençant par "indiquer"/"préciser",
ou contenant des guillemets `«`, est SYSTÉMATIQUEMENT marqué `A_CONFIRMER` —
jamais résolu automatiquement.

Cas `duree` vs `nombre` : le placeholder brut est souvent juste `(nombre)`
(ex. "(nombre) jours") — l'unité de durée est HORS parenthèses, dans le texte
qui suit. La règle regarde donc les ~20 caractères qui suivent la parenthèse
fermante pour détecter un mot d'unité de durée (jours/mois/ans/...) avant de
trancher `nombre` vs `duree` — toujours une règle explicite sur le texte
visible, jamais un jugement sémantique.
"""
import argparse
import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data" / "pacte_fondateurs"
_PLACEHOLDER_RE = re.compile(r"\(([^)]+)\)")
_DUREE_UNITS = (
    "jour", "jours", "mois", "an", "ans", "année", "années",
    "semaine", "semaines", "trimestre", "trimestres", "semestre", "semestres",
)
_AMBIGU_MARKERS = ("indiquer", "préciser", "«")
# "trente (30) jours", "dénommé(e)s", "sauf (a) avec...", "(i)/(ii)/(iii)" —
# le modèle Bpifrance répète un nombre déjà écrit en lettres entre
# parenthèses, ou utilise une parenthèse pour l'accord grammatical ou une
# énumération. Rien à remplir dans ces cas — CE N'EST PAS un placeholder,
# contrairement à "(Ville)" ou "(Xème)" qui restent, eux, de vrais
# emplacements à saisir.
_NUMERIC_RE = re.compile(r"^\d+$")
_SINGLE_LETTER_RE = re.compile(r"^[a-zA-Zà-ÿ]$")
_ROMAN_NUMERAL_RE = re.compile(r"^(i|ii|iii|iv|v|vi|vii|viii|ix|x)$", re.IGNORECASE)
_ORDINAL_PLACEHOLDER_RE = re.compile(r"^x[eè]me$", re.IGNORECASE)
# Signaux d'une note de rédaction ou d'une précision explicative glissée dans
# le texte entre parenthèses — PAS un placeholder à remplir, PAS non plus une
# variable "choix"/"reference_croisee" (déjà couvert par _AMBIGU_MARKERS).
# Trouvé en relisant les 59 valeurs uniques classées "texte" avant correctif
# (voir échange du 20/09/2026) : "(à compléter)", "(insérer une formule...)",
# "(notamment dans le cadre d'une souscription)", "(et de ses Filiales)"...
# — trop hétérogène pour une règle unique fiable, donc large filet plutôt
# qu'une classification silencieuse en "texte".
_INSTRUCTION_MARKERS = (
    "à compléter", "insérer", "notamment", "y compris", "le cas échéant",
    "à l'exception", "à l’exception", "ne doit pas excéder", "pour une ",
    "pour définir", "compte tenu", "…",
)


def _slugify(texte: str) -> str:
    s = texte.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def classify(libelle: str, texte_suivant: str) -> str:
    t = libelle.strip()
    tl = t.lower()

    if _NUMERIC_RE.match(t) or _SINGLE_LETTER_RE.match(t) or _ROMAN_NUMERAL_RE.match(t):
        return "NON_VARIABLE"

    # Artefact de parenthèses imbriquées : "(dénommé(e)s)" contient une
    # parenthèse ouvrante à l'intérieur du texte capturé — _PLACEHOLDER_RE
    # (non récursive) s'arrête à la première fermante et capture
    # "dénommé(e" au lieu du texte complet. Un vrai placeholder ne contient
    # jamais lui-même une parenthèse ouvrante — trouvé en relisant les
    # valeurs uniques classées "texte" (voir échange du 20/09/2026).
    if "(" in t:
        return "NON_VARIABLE"

    # Choix locaux ("minoritaire/majoritaire") vs renvois croisés auto-résolus
    # ("préemption/préférence") : indiscernables par le texte du placeholder
    # seul — JAMAIS deviné, voir docstring du module.
    if "/" in t or any(tl.startswith(m) or m in tl for m in _AMBIGU_MARKERS):
        return "A_CONFIRMER"

    if any(marker in tl for marker in _INSTRUCTION_MARKERS):
        return "A_CONFIRMER"

    # Un vrai placeholder de ce modèle est un groupe nominal court (1 à 4
    # mots : "adresse", "siège social", "nom de la société"...). Un texte plus
    # long, ou qui contient " ou " (signe d'une clarification insérée dans la
    # phrase plutôt qu'un blanc à remplir, ex. "(et de ses Filiales)",
    # "(directement ou indirectement)"), n'a montré aucun vrai placeholder
    # dans la relecture manuelle — filet large plutôt qu'une classification
    # silencieuse en "texte".
    if len(t.split()) > 4 or " ou " in tl or tl.startswith("ou "):
        return "A_CONFIRMER"

    # Limites de mot partout ci-dessous : "rang" en sous-chaîne matchait
    # "étranger" avant correctif (bug trouvé le 20/09/2026 en relisant les
    # valeurs uniques par type avant de livrer ce script).
    if _ORDINAL_PLACEHOLDER_RE.match(t) or re.search(r"\brang\b", tl) or re.search(r"\bordinal\b", tl):
        return "nombre_ordinal"

    if re.search(r"\bdate\b", tl):
        return "date"

    if re.search(r"\bmontant\b", tl) or re.search(r"\bcapital\b", tl) or "€" in t:
        return "montant"

    if tl == "nombre":
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
                "article_numero": segment["article_numero"],
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
