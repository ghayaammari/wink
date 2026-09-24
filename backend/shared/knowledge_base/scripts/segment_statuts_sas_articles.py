"""Segmentation structurelle (Phase 1, sous-étape 1a), service 1.1.4 statuts SAS.
Lit la sortie de `extract_statuts_sas_raw.py` (lignes brutes) et la découpe en
segments, SANS ENCORE décider quelle hiérarchie (article / variante) chaque
segment représente — même principe que `segment_pacte_fondateurs_articles.py`
(1.1.13) : purement mécanique, sur des marqueurs visibles dans le texte,
aucun jugement sémantique à cette étape.

Lancement, depuis `wink/` :

    python -m backend.shared.knowledge_base.scripts.segment_statuts_sas_articles \
        --label modele_sas

Lit `data/statuts_sas_raw/raw_<label>.json`, écrit
`data/statuts_sas_raw/segmented_<label>.json`.

MARQUEURS — vérifiés sur le texte réel extrait (22/09/2026, 1048 lignes),
différents de ceux du pacte (`Article <n>` + `*`) :
1. `titre_partie` — une ligne qui commence par un numéro romain suivi de
   `.`/`-`/`–` (ex. "I. – FORME - OBJET..."). 8 occurrences — ce sont les
   grandes parties du document (Forme, Apports, Gouvernance...), un niveau
   au-dessus de l'article. Pas de contenu juridique en soi, juste un titre de
   regroupement — conservé pour la traçabilité, pas pour la clause finale.
2. `titre_article` — une ligne qui commence par `Article <numéro>` (même
   regex que le pacte, `\\s+` tolère les doubles espaces réels du PDF :
   "Article  1 - . Forme"). 46 occurrences.
3. `variante` — une ligne qui commence par `›` : introduit une rédaction
   alternative (ex. "› En cas de transfert par le Président sans
   ratification..."). Équivalent du `*Hypothèse` du pacte. 49 occurrences.
4. `ajout_optionnel` — une ligne qui commence par `+` : un ajout facultatif
   au texte de base (ex. "+ Si un sigle a été choisi, ajouter :"), PAS un
   choix entre rédactions alternatives (différence avec `variante` à garder
   en tête pour la Phase 1b : une `variante` REMPLACE, un `ajout_optionnel`
   COMPLÈTE). 53 occurrences.
5. `separateur_ou` — une ligne strictement égale à "Ou" : sépare 2
   `variante` consécutives dans le même choix. 26 occurrences — n'ouvre PAS
   un nouveau segment de contenu, juste un marqueur de coupure entre 2
   variantes déjà détectées par ailleurs (voir `segment_paragraphs` : une
   ligne "Ou" termine le segment `variante` courant, comme un `titre_article`
   le ferait, mais sans démarrer de nouveau segment à la place — la variante
   suivante commence son propre segment à la prochaine ligne `›`).

Les puces (`•`) et les tirets d'énumération NE sont PAS des marqueurs de
segment ici (contrairement à une intuition possible) — ce sont de simples
énumérations à l'intérieur d'un article (ex. les 3 puces de l'objet social,
Article 2) : elles restent dans les paragraphes du segment courant, comme
n'importe quelle ligne de contenu.

POURQUOI toujours pas de regroupement par hiérarchie ici (comme pour le
pacte) : certains `titre_article` contiennent PLUSIEURS variantes/ajouts
imbriqués (ex. Article 4 Siège social : 4 variantes `›` qui se substituent
l'une à l'autre pour la clause de transfert de siège) — décider laquelle est
top-level vs. imbriquée demande de relire le résultat, pas de le deviner ici.

CORRECTION DE NUMÉROTATION (ajoutée le 22/09/2026, décision utilisateur) :
le PDF Bpifrance source numérote deux articles consécutifs "18" ("Location
d'actions" puis "Modification dans le contrôle d'une société associée") —
vérifié : pas un bug de ce script, une erreur du document source lui-même
(46 titres `Article <n>` pour seulement 45 numéros distincts). Corrigé ICI,
mécaniquement, par POSITION dans le document plutôt qu'en retapant un
chiffre à la main : le n-ième `titre_article` rencontré devient l'article
numéro n. `article_numero` porte désormais ce numéro CORRIGÉ (celui à
utiliser partout en aval — `code_section`, `ordre`...) ; le numéro tel
qu'imprimé dans le PDF est conservé à part dans `article_numero_imprime`,
pour la traçabilité.

Cette correction structurelle ne suffit PAS à elle seule : le texte lui-même
contient des renvois internes ("l'article 27 des présents statuts") qui
utilisent le numéro IMPRIMÉ (fautif) et devront être corrigés au moment où
chaque `texte_clause` sera composé (Phase 1b/2, pas ici — modifier le texte
brut extrait casserait la fidélité vérifiable à la source). Ce script se
contente de les REPÉRER (recherche de "article <n>" dans tout le corps du
texte, n <= 46 pour écarter les renvois vers un autre code — Code civil
art. 1843, Code de commerce L.227-1... qui utilisent des numéros à 3-4
chiffres ou des préfixes L./D.) et de calculer leur correction attendue,
écrites dans `data/statuts_sas_raw/renvois_articles_a_corriger_<label>.json`
— une checklist pour la Phase 1b, pas une réécriture automatique. Un renvoi
qui cible le numéro imprimé "18" (ambigu entre les 2 occurrences) serait
signalé `NON_RESOLU` plutôt que deviné — vérifié : aucun cas de ce type dans
ce document.
"""
import argparse
import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data" / "statuts_sas_raw"
_ARTICLE_RE = re.compile(r"^Article\s+(\d+)")
_PARTIE_RE = re.compile(r"^([IVXLC]+)\s*[.\-–]")
# Renvoi interne dans le corps du texte, ex. "l'article  27 des présents
# statuts" ou "l'article 21 -4 ci-dessus" — 1 ou 2 chiffres seulement (les
# renvois vers un autre code utilisent 3-4 chiffres : "article 1843").
_RENVOI_RE = re.compile(r"[Aa]rticle\s*\.?\s*(\d{1,2})(?!\d)")


def _type_ligne(texte: str) -> str | None:
    stripped = texte.strip()
    if _ARTICLE_RE.match(stripped):
        return "titre_article"
    if _PARTIE_RE.match(stripped):
        return "titre_partie"
    if stripped.startswith("›"):
        return "variante"
    if stripped.startswith("+"):
        return "ajout_optionnel"
    if stripped == "Ou":
        return "separateur_ou"
    return None


def segment_paragraphs(paragraphes: list[dict]) -> list[dict]:
    segments: list[dict] = []
    current: dict | None = None

    for p in paragraphes:
        texte = p["texte"]
        type_ligne = _type_ligne(texte)

        if type_ligne == "separateur_ou":
            # Ferme le segment courant (typiquement une `variante`) sans en
            # ouvrir un nouveau : la variante suivante ouvrira le sien à sa
            # propre ligne `›`. Voir docstring, point 5.
            if current is not None:
                segments.append(current)
            current = None
            continue

        if type_ligne is not None:
            if current is not None:
                segments.append(current)
            article_match = _ARTICLE_RE.match(texte.strip())
            current = {
                "type": type_ligne,
                "article_numero": int(article_match.group(1)) if article_match else None,
                "paragraphes": [p],
            }
        else:
            if current is None:
                # Texte avant tout marqueur (ex. formule d'entrée "Les
                # soussignés,", identification des fondateurs) — segment
                # "hors marqueur", pas une erreur, même traitement que le
                # pacte.
                current = {"type": "hors_marqueur", "article_numero": None, "paragraphes": []}
            current["paragraphes"].append(p)

    if current is not None:
        segments.append(current)

    return segments


def renumber_articles(segments: list[dict]) -> dict[int, int]:
    """Corrige `article_numero` sur les segments `titre_article`, en place,
    par POSITION dans le document (voir docstring du module). Conserve le
    numéro imprimé original dans `article_numero_imprime`. Retourne le
    mapping {numero_imprime: numero_corrige} — imparfait pour le numéro
    dupliqué "18" (2 clés possibles pour la même valeur imprimée), donc
    UNIQUEMENT utilisable pour corriger les renvois dont le numéro imprimé
    n'est PAS 18 (le seul cas ambigu, vérifié absent du texte — voir
    `find_renvois_a_corriger`).
    """
    mapping: dict[int, int] = {}
    position = 0
    for s in segments:
        if s["type"] != "titre_article":
            continue
        position += 1
        imprime = s["article_numero"]
        s["article_numero_imprime"] = imprime
        s["article_numero"] = position
        if imprime != 18:  # le 18 dupliqué n'a pas un mapping unique, exclu volontairement
            mapping[imprime] = position
    return mapping


def find_renvois_a_corriger(paragraphes: list[dict], mapping: dict[int, int]) -> list[dict]:
    """Repère, dans TOUT le corps du texte (pas seulement les titres), les
    renvois internes à un numéro d'article qui a changé — voir docstring du
    module. Ne modifie rien, produit une checklist pour la Phase 1b."""
    renvois = []
    for p in paragraphes:
        if _ARTICLE_RE.match(p["texte"].strip()):
            # C'est un TITRE d'article ("Article 27 - . Modalités..."), pas
            # un renvoi dans le corps du texte — déjà traité par
            # renumber_articles(), à ne pas compter une 2e fois ici.
            continue
        # Un renvoi à un article non encore écrit par l'entrepreneur (ex.
        # "l'article .....(numéro de l'article des statuts prévoyant...)")
        # n'est pas un numéro littéral — le regex ne matche que des chiffres,
        # donc ces placeholders sont naturellement ignorés ici.
        for m in _RENVOI_RE.finditer(p["texte"]):
            imprime = int(m.group(1))
            if imprime == 18:
                statut, corrige = "NON_RESOLU", None
            elif imprime in mapping:
                corrige = mapping[imprime]
                statut = "A_CORRIGER" if corrige != imprime else "INCHANGE"
            else:
                # Numéro non reconnu comme un article de ce document (ex.
                # renvoi vers un autre code, pas filtré par le nb de
                # chiffres — laissé de côté, à vérifier manuellement si utile).
                continue
            if statut == "INCHANGE":
                continue
            renvois.append(
                {
                    "page": p["page"],
                    "index": p["index"],
                    "texte": p["texte"],
                    "numero_imprime_trouve": imprime,
                    "numero_corrige_attendu": corrige,
                    "statut": statut,
                }
            )
    return renvois


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="Doit correspondre à un raw_<label>.json déjà extrait.")
    args = parser.parse_args()

    inpath = _DATA_DIR / f"raw_{args.label}.json"
    with open(inpath, encoding="utf-8") as f:
        raw = json.load(f)

    segments = segment_paragraphs(raw["paragraphes"])
    mapping = renumber_articles(segments)
    renvois = find_renvois_a_corriger(raw["paragraphes"], mapping)

    outpath = _DATA_DIR / f"segmented_{args.label}.json"
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"source_file": args.label, "segments": segments}, f, ensure_ascii=False, indent=2)

    renvois_path = _DATA_DIR / f"renvois_articles_a_corriger_{args.label}.json"
    with open(renvois_path, "w", encoding="utf-8") as f:
        json.dump({"source_file": args.label, "renvois": renvois}, f, ensure_ascii=False, indent=2)

    par_type: dict[str, int] = {}
    for s in segments:
        par_type[s["type"]] = par_type.get(s["type"], 0) + 1
    print(f"OK — {len(segments)} segment(s) -> {outpath}")
    print(f"   dont : {par_type}")
    print(
        f"   renumérotation : {sum(1 for k, v in mapping.items() if k != v)} article(s) décalé(s) "
        f"(voir article_numero_imprime pour le numéro original)"
    )
    print(f"   renvois internes à corriger en Phase 1b : {len(renvois)} -> {renvois_path}")
    for r in renvois:
        if r["statut"] == "NON_RESOLU":
            print(f"   ⚠ NON_RESOLU (numéro '18' ambigu) : page {r['page']} — {r['texte'][:80]}")


if __name__ == "__main__":
    main()
