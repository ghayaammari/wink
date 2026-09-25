# -*- coding: utf-8 -*-
"""Script de contrôle (service 1.1.13, consolidation Articles 1-3) : vérifie
que chaque paragraphe / annotation d'un article source
(`articles_consolides_modele_principal.json`) est bien couvert par au moins
une entrée de `decisions_articles.json`, via les champs `paragraphes_source`
et `annotations_source`.

Pourquoi : les vérifications du générateur (`generate_pacte_fondateurs_v2.py`)
contrôlent la cohérence interne des placeholders, mais ne peuvent pas
détecter qu'un paragraphe entier a été oublié en recopiant le texte source
(bug trouvé sur l'Article 1 -- "Outre les termes définis dans le corps du
texte." absent). ATTENTION : ce script contrôle la COUVERTURE (rien
d'oublié), pas la FIDÉLITÉ du texte recopié (un mot altéré dans un paragraphe
par ailleurs bien référencé ne sera pas détecté ici) -- les deux contrôles
sont complémentaires, pas substituables.

Usage : python3 verifier_traceabilite_article.py [numero_article ...]
        (sans argument : contrôle tous les articles présents dans
        decisions_articles.json)
"""
import json
import sys
from pathlib import Path

DECISIONS = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/decisions_articles.json")
CONSOLIDES = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/articles_consolides_modele_principal.json")

# Index dont on sait, après revue humaine, qu'ils ne doivent PAS apparaître
# dans le document final -- consignés ici plutôt que silencieusement ignorés,
# pour que ce ne soit pas un simple "oubli" caché. Deux catégories :
# (a) instructions internes Bpifrance à l'auteur du pacte ("Choisir parmi les
#     clauses suivantes :") -- jamais du texte client ;
# (b) répétitions du titre d'article dans chacune des 7 hypothèses de
#     l'Article 3 (Bpifrance présente 7 brouillons complets alternatifs,
#     chacun réaffirme son propre "Article 3 - ...") -- redondant depuis
#     l'ajout du titre d'article unique (`titres_articles`).
EXCLUSIONS_LEGITIMES = {
    2: {48: "instruction interne Bpifrance (\"Choisir parmi les clauses suivantes :\")"},
    3: {
        70: "instruction interne Bpifrance (\"Choisir ici entre 7 clauses alternatives...\")",
        72: "répétition du titre d'article dans l'Hypothèse 1 -- couverte par titres_articles",
        104: "répétition du titre d'article dans l'Hypothèse 2 -- couverte par titres_articles",
        140: "répétition du titre d'article dans l'Hypothèse 3 -- couverte par titres_articles",
        160: "répétition du titre d'article dans l'Hypothèse 4 -- couverte par titres_articles",
        169: "répétition du titre d'article dans l'Hypothèse 5 -- couverte par titres_articles",
        178: "répétition du titre d'article dans l'Hypothèse 6 -- couverte par titres_articles",
        189: "répétition du titre d'article dans l'Hypothèse 7 -- couverte par titres_articles",
    },
    5: {
        235: "instruction interne Bpifrance (\"*Hypothèse 1 : ... indiquer :\")",
        242: "instruction interne Bpifrance (\"*Hypothèse 2 : ... indiquer par :\")",
        246: "instruction interne Bpifrance (\"*Hypothèse 3 : ... indiquer :\")",
    },
    6: {
        250: "commentaire éditorial Bpifrance sur les clauses de retrait en général -- explication pour le rédacteur, pas texte contractuel (cohérent avec v1, qui ne l'a pas repris)",
        251: "commentaire éditorial Bpifrance sur la validité juridique des clauses de retrait -- idem",
        252: "commentaire éditorial Bpifrance sur la validité juridique des clauses de rachat/sortie alternative -- idem",
        253: "instruction interne Bpifrance (\"Hypothèse 1 : en cas de droit de retrait sans condition...\")",
        265: "instruction interne Bpifrance (\"Hypothèse 2 : en cas de droit de retrait conditionnel...\")",
    },
    8: {
        347: "instruction interne Bpifrance (Redaction A, indiquer)",
        349: "instruction interne Bpifrance (Redaction B, remplacer par)",
    },
    10: {
        460: "commentaire éditorial Bpifrance sur la durée du pacte (limite légale, art. L.227-13/1844-5) -- explication pour le rédacteur, pas texte contractuel",
    },
}


def main() -> None:
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    consolides = json.loads(CONSOLIDES.read_text(encoding="utf-8"))

    articles_source = {a["article"]: a for a in consolides["articles"]}
    titres_articles = decisions.get("titres_articles", {})

    # articles à contrôler : ceux qui ont au moins une entrée avec un champ
    # de traçabilité renseigné (les articles pas encore traités n'ont
    # simplement pas d'entrée -- on ne les signale pas comme "en échec").
    demandes = sys.argv[1:]
    if demandes:
        cibles = set()
        for d in demandes:
            cibles.add(int(d) if d.isdigit() else d)
    else:
        cibles = {a["article"] for a in decisions["articles"]
                   if a.get("paragraphes_source") or a.get("annotations_source")}

    total_erreurs = 0

    for article_id in sorted(cibles, key=str):
        source = articles_source.get(article_id)
        if source is None:
            print(f"[{article_id}] introuvable dans articles_consolides_modele_principal.json -- ignoré")
            continue

        index_paragraphes_source = {p["index"] for p in source.get("paragraphes", [])}
        index_annotations_source = {p["index"] for p in source.get("annotations", [])}
        textes_par_index = {p["index"]: p["texte"] for p in source.get("paragraphes", []) + source.get("annotations", [])}

        entrees = [e for e in decisions["articles"] if e.get("article") == article_id]

        couverts_paragraphes = set()
        couverts_annotations = set()
        codes_par_index = {}
        for e in entrees:
            for i in e.get("paragraphes_source", []):
                couverts_paragraphes.add(i)
                codes_par_index.setdefault(i, []).append(e["code"])
            for i in e.get("annotations_source", []):
                couverts_annotations.add(i)
                codes_par_index.setdefault(i, []).append(e["code"])

        # Titre d'article (`titres_articles`) : couvre lui aussi des index
        # de paragraphes, séparément des entrées de contenu.
        titre_info = titres_articles.get(str(article_id))
        if titre_info:
            for i in titre_info.get("paragraphes_source", []):
                couverts_paragraphes.add(i)
                codes_par_index.setdefault(i, []).append(f"titres_articles[{article_id}]")

        exclusions = EXCLUSIONS_LEGITIMES.get(article_id, {})

        # index déclarés par une entrée mais qui n'existent pas dans la
        # source (coquille de saisie -- code invalide/faux numéro)
        fantomes_p = couverts_paragraphes - index_paragraphes_source
        fantomes_a = couverts_annotations - index_annotations_source

        oublies_p = index_paragraphes_source - couverts_paragraphes - exclusions.keys()
        oublies_a = index_annotations_source - couverts_annotations - exclusions.keys()
        exclus_presents = (index_paragraphes_source | index_annotations_source) & exclusions.keys()

        n_erreurs = len(fantomes_p) + len(fantomes_a) + len(oublies_p) + len(oublies_a)
        total_erreurs += n_erreurs

        statut = "OK" if n_erreurs == 0 else f"{n_erreurs} écart(s)"
        print(f"[Article {article_id}] {len(entrees)} entrée(s) -- {statut}"
              + (f" ({len(exclus_presents)} exclusion(s) documentée(s))" if exclus_presents else ""))

        for i in sorted(oublies_p):
            print(f"    !! paragraphe {i} jamais référencé : {textes_par_index.get(i, '')[:90]}")
        for i in sorted(oublies_a):
            print(f"    !! annotation {i} jamais référencée : {textes_par_index.get(i, '')[:90]}")
        for i in sorted(exclus_presents):
            print(f"    .. index {i} exclu (documenté) : {exclusions[i]}")
        for i in sorted(fantomes_p):
            print(f"    !! paragraphes_source={i} référencé par {codes_par_index[i]} mais absent de la source")
        for i in sorted(fantomes_a):
            print(f"    !! annotations_source={i} référencé par {codes_par_index[i]} mais absent de la source")

    print()
    if total_erreurs:
        print(f"ÉCHEC -- {total_erreurs} écart(s) de traçabilité au total")
        sys.exit(1)
    else:
        print("OK -- couverture complète pour les articles contrôlés")


if __name__ == "__main__":
    main()
