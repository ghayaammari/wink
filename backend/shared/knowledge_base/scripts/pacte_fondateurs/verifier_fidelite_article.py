# -*- coding: utf-8 -*-
"""Script de contrôle (service 1.1.13, consolidation Articles 1-3, volet 2 de
la traçabilité) : vérifie la FIDÉLITÉ du texte recopié dans
`decisions_articles.json`, pas seulement sa couverture (déjà faite par
`verifier_traceabilite_article.py`).

Pour chaque entrée marquée `recopie_directe: true`, reconstruit le texte
source attendu à partir de `paragraphes_source` + `annotations_source`
(triés par index -- valable seulement quand la recopie est directe, sans
fusion/réordonnancement), le normalise (espaces/insécables uniformisés,
tout `(...)` réduit à un jeton neutre "(X)" puisque le renommage des
placeholders est volontaire), et le compare au `texte` normalisé de
l'entrée. Signale tout écart au-delà du jeton de placeholder -- mot
supprimé, ajouté ou changé.

Les entrées `recopie_directe: false` (Article 3 : les 11 clauses de
préemption/préférence, reconstruites par fusion/découpage depuis v1) sont
listées mais pas diffées ici -- un diff mot à mot y est trop bruyant pour
être utile (voir `verifier_fidelite_v1_article3.py`, qui a fait ce contrôle
une fois, ponctuellement, sur le maillon v1).

Usage : python3 verifier_fidelite_article.py [numero_article ...]
"""
import difflib
import json
import re
import sys
from pathlib import Path

DECISIONS = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/decisions_articles.json")
CONSOLIDES = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/articles_consolides_modele_principal.json")

SEUIL_ALERTE = 0.97  # en dessous de cette similarité normalisée, l'entrée est signalée

# Entrées déjà revues manuellement dont l'écart est légitime (en-tête
# "* Option N :"/"Ajouter le cas échéant :" supprimé, ponctuation ajustée
# lors du passage liste à puces -> clause autonome) -- documenté plutôt que
# re-signalé à chaque exécution. Toute NOUVELLE entrée sous le seuil reste
# signalée normalement.
ALERTES_ACCEPTEES = {
    "preambule_sans_investisseurs": "variante volontairement expurgée des mentions Investisseurs",
    "cessions_libres_chapeau": "instruction éditoriale \"(ajouter si...)\" supprimée",
    "cession_libre_fonds_lie_investisseur_solidarite": "en-tête \"Ajouter le cas échéant :\" supprimé",
    "cession_libre_investisseur_apres_date": "ponctuation/majuscule ajustées (liste à puces -> clause autonome)",
    "inalienabilite_totale_parties": "en-tête de section + instruction \"* Option 1 :\" supprimés",
    "inalienabilite_fondateurs_seuls": "en-tête \"* Option 2 :\" + clause accord-investisseurs supprimés (scindés ailleurs)",
    "inalienabilite_fondateurs_partielle_plafond": "en-tête \"* Option 3 :\" + clause accord-investisseurs supprimés (scindés ailleurs)",
    "limitation_participations": "en-tête \"* Option 4 :\" supprimé",
    "promesse_leaver_engagement": "3 corrections du texte source (21/09/2026) : (i) duplication Associes Fondateurs / Associes fondateurs dans la meme phrase (coquille Bpifrance) -- gardee une seule fois ; (ii) su -> du (coquille de frappe evidente Bpifrance, Pour les besoins su present article) ; (iii) organe de gouvernance (3 occurrences) parametre via reference_croisee vers Article 8 au lieu d un texte fixe.",
}


def norm(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = re.sub(r"\([^()]*\)", "(X)", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main() -> None:
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    consolides = json.loads(CONSOLIDES.read_text(encoding="utf-8"))
    articles_source = {a["article"]: a for a in consolides["articles"]}

    demandes = sys.argv[1:]
    if demandes:
        cibles = {int(d) if d.isdigit() else d for d in demandes}
    else:
        cibles = {a["article"] for a in decisions["articles"] if "recopie_directe" in a}

    n_ok = n_alerte = n_ignoree = 0

    for entry in decisions["articles"]:
        if entry.get("article") not in cibles:
            continue
        if "recopie_directe" not in entry:
            continue
        if not entry["recopie_directe"]:
            print(f"-- {entry['code']} : recopie_directe=false, diff non pertinent (voir script dédié si besoin)")
            n_ignoree += 1
            continue

        source = articles_source.get(entry["article"])
        if source is None:
            print(f"!! {entry['code']} : article source '{entry['article']}' introuvable -- ignoré")
            continue
        textes_par_index = {p["index"]: p["texte"] for p in source.get("paragraphes", []) + source.get("annotations", [])}

        indices = sorted(entry.get("paragraphes_source", []) + entry.get("annotations_source", []))
        if not indices:
            continue

        texte_source = norm(" ".join(textes_par_index.get(i, "") for i in indices))
        texte_entry = norm(entry.get("texte", ""))

        ratio = difflib.SequenceMatcher(None, texte_source, texte_entry).ratio()

        if ratio >= SEUIL_ALERTE:
            n_ok += 1
            continue

        if entry["code"] in ALERTES_ACCEPTEES:
            n_ok += 1
            print(f".. {entry['code']} : similarité {ratio:.3f}, écart accepté (documenté) : {ALERTES_ACCEPTEES[entry['code']]}")
            continue

        n_alerte += 1
        print(f"!! {entry['code']} : similarité normalisée {ratio:.3f} (< {SEUIL_ALERTE})")
        sm = difflib.SequenceMatcher(None, texte_source.split(), texte_entry.split())
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            src_frag = " ".join(texte_source.split()[i1:i2])
            entry_frag = " ".join(texte_entry.split()[j1:j2])
            print(f"    [{tag}] SOURCE : {src_frag[:100]!r}")
            print(f"           ENTREE : {entry_frag[:100]!r}")
        print()

    print(f"\n{n_ok} entrée(s) OK, {n_alerte} alerte(s), {n_ignoree} non pertinente(s) (recopie_directe=false)")
    if n_alerte:
        sys.exit(1)


if __name__ == "__main__":
    main()
