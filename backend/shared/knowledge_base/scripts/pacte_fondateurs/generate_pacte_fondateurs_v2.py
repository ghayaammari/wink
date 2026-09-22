"""Script générateur (correction méthodologique, service 1.1.13, 21/09/2026) :
produit les fichiers finaux `_v2` à partir de `decisions_articles.json`, au
lieu qu'ils soient tapés à la main directement dans leur format final.

Pourquoi : c'est l'écriture manuelle des JSON finaux (sans passer par un
format intermédiaire simple) qui a produit les trous de la v1 (variables
`reference_croisee` jamais branchées, placeholders dupliqués non détectés
avant qu'un utilisateur ne pose la question). `decisions_articles.json` reste
un format court, lisible, où chaque article = une décision de contenu
(texte nettoyé + variables) -- ce script fait tout le travail mécanique
répétitif (structure des 2 fichiers de sortie, vérifications) qu'un humain
peut oublier de refaire à chaque article.

Vérifications automatiques (bloquent la génération si échec, plutôt que de
produire un fichier silencieusement incorrect) :
  1. chaque `libelle` de variable doit apparaître EXACTEMENT une fois dans le
     texte de son article, sous la forme littérale "(libelle)" -- 0 fois =
     variable orpheline (jamais utilisée dans le texte), >1 fois = placeholder
     ambigu (le bug trouvé et corrigé à la main sur le Préambule -- ce script
     le détecte désormais tout seul pour CHAQUE article, sans qu'on ait à y
     repenser) ;
  2. tout texte "(...)" restant dans le texte d'un article qui ne correspond
     à AUCUNE variable déclarée est signalé -- probablement un placeholder
     Bpifrance oublié dans `decisions_articles.json`.

Ajout Article 2 (21/09/2026) -- `comportement_section` par entrée :
  - "mention_obligatoire" (défaut, comme avant) : 1 entrée = 1 clause = 1
    section, toujours affichée.
  - "clause_optionnelle" : 1 entrée = 1 clause = 1 section, mais l'associé
    choisit de l'inclure ou non (ex. les 5 cas de "Cessions Libres" à
    l'article 2.1 -- le texte Bpifrance dit explicitement "Choisir parmi les
    clauses suivantes", ce n'est pas un bloc fixe unique comme la v1 le
    modélisait). Peut porter `explication` (texte d'aide affiché à
    l'utilisateur) et/ou `conditions_affichage.depend_de_section` +
    `depend_de_variantes` pour un sous-choix qui n'a de sens que si une autre
    clause optionnelle précise a été retenue (ex. la phrase de solidarité des
    Investisseurs, qui ne s'affiche que si la clause "cession à un fonds lié"
    a été choisie).
  - "variante_obligatoire" : plusieurs entrées partagent un `groupe_section`
    commun -- une seule section est générée, avec `variantes_candidates` =
    la liste de leurs `code`, l'associé choisit UNE des variantes (ex. les 4
    options d'inaliénabilité de l'article 2.2, déjà ce schéma en v1).
    `titre_section`/`explication_section` (mis sur au moins une des entrées
    du groupe) deviennent le titre/l'explication de la section groupée.

Sortie :
  - `backend/entrepreneur/scripts/data/pacte_fondateurs_bpifrance_clauses_v2.json`
  - `backend/entrepreneur/scripts/data/pacte_fondateurs_document_templates_v2.json`
  - `backend/entrepreneur/scripts/data/pacte_fondateurs_validity_criteria_v2.json`
Uniquement les articles présents dans `decisions_articles.json` -- les
articles pas encore traités n'apparaissent simplement pas encore en sortie
(pas de placeholder vide généré à leur place).

Ajout validity_criteria (21/09/2026) -- une entrée `decisions_articles.json`
de cible "clause" peut porter un champ `validity_criteria` (liste de
`{type_critere, description_critere, valeur_limite, base_legale}`) : une
règle de validité légale rattachée à cette clause (ex. durée max 10 ans,
prix déterminable). Le générateur y ajoute `code_clause` automatiquement
(pas dupliqué à la main) et les rassemble dans le fichier `_v2` dédié --
même principe que le reste du pipeline : la donnée métier dans
`decisions_articles.json`, l'assemblage mécanique par ce script.
"""
import json
import re
from pathlib import Path

DECISIONS = Path("backend/shared/knowledge_base/scripts/data/pacte_fondateurs/decisions_articles.json")
CLAUSES_OUT = Path("backend/entrepreneur/scripts/data/pacte_fondateurs_bpifrance_clauses_v2.json")
TEMPLATES_OUT = Path("backend/entrepreneur/scripts/data/pacte_fondateurs_document_templates_v2.json")
VALIDITY_OUT = Path("backend/entrepreneur/scripts/data/pacte_fondateurs_validity_criteria_v2.json")

PLACEHOLDER_RE = re.compile(r"\(([^()]+)\)")

# Marqueurs d'énumération juridique standards ("(i)", "(ii)", ...) : ressemblent
# à un placeholder court (<=4 mots, pas de " ou ") mais n'en sont pas -- trouvé
# en écrivant l'Article 2 (clause "cession à un fonds lié à un Investisseur",
# qui reprend les "(i)/(ii)/(iii)" du texte Bpifrance d'origine).
MARQUEURS_ENUMERATION = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def _ressemble_a_un_placeholder(contenu: str) -> bool:
    """Même filtre que `classify()` dans `extract_pacte_fondateurs_variables.py`
    (NON_VARIABLE / A_CONFIRMER) : un vrai placeholder Bpifrance est un groupe
    nominal court (<=4 mots), sans " ou " ni parenthèse imbriquée -- un texte
    entre parenthèses plus long, ou une clarification en langue normale
    ("(ci-après désignée la « Société »)", "(ou l'une quelconque de ses
    filiales)"), fait partie de la phrase elle-même, ce n'est pas un blanc à
    remplir. Réutilisé ici plutôt que réinventé -- évite de re-signaler à tort
    des parenthèses parfaitement normales du texte Bpifrance (trouvé en
    testant ce script sur le Préambule et l'Article 1). Exclut aussi les
    marqueurs d'énumération romains (i)/(ii)/(iii) (trouvé sur l'Article 2).
    """
    t = contenu.strip()
    tl = t.lower()
    if tl in MARQUEURS_ENUMERATION:
        return False
    if "(" in t:
        return False
    # Marqueurs d'accord grammatical français ("Titre(s)", "au(x)",
    # "le(s) associé(s)") : une seule lettre entre parenthèses, jamais un
    # vrai placeholder Bpifrance (trouvé sur l'Article 3).
    if len(t) <= 1:
        return False
    # Nom usuel d'une clause donné entre parenthèses dans un titre Bpifrance
    # ("(Clause de drag-along)", "(Clause de sortie forcée)") : toujours
    # <= 4 mots donc sinon pris pour un blanc à remplir -- ce n'est pas un
    # choix à faire, juste le nom courant de la clause (trouvé sur
    # l'Article 5, titre "5.1 ... (Clause de drag-along)").
    if tl.startswith("clause de ") or tl.startswith("clause d'"):
        return False
    # Définition de terme entre guillemets français, avec au plus un article
    # court devant ("(« PROMESSE LEAVER »)", "(le « Mandataire »)") -- même
    # famille que les définitions déjà exclues plus loin par la règle
    # "longueur > 4 mots" quand elles sont plus longues (ex. "(la « Promesse
    # de Vente »)") : celle-ci couvre les cas où la définition tient en <= 4
    # mots et passerait sinon les autres filtres (trouvé sur l'Article 9,
    # "PROMESSE LEAVER"). Toujours du texte fixe, jamais un blanc à remplir --
    # cases 89-94/98 du triage, même famille que 1/10/57.
    if re.match(r"^(le |la |les |l['’])?«.*»$", t):
        return False
    # Nombre déjà fixé par Bpifrance, écrit en toutes lettres ET en chiffres
    # ("trente (30) jours") -- convention juridique française courante, pas
    # un blanc : contrairement à "(nombre) jours" ailleurs dans le même
    # modèle, ici le chiffre est déjà choisi, il ne reste rien à saisir
    # (trouvé sur l'Article 7, "délai maximum de trente (30) jours").
    if t.isdigit():
        return False
    mots = tl.split()
    if len(mots) > 4 or " ou " in tl or tl.startswith("ou ") or tl.startswith("et "):
        # 'et ' : même famille que 'ou ' juste au-dessus -- courte clarification
        # conjonctive ajoutée entre parenthèses ('(et de ses Filiales)', à côté
        # de '(ou une Filiale)' déjà exclu) -- fait partie de la phrase, pas un
        # blanc (trouvé sur l'Article 9, engagement propriété intellectuelle).
        return False
    # Clarification en langue normale introduite par une conjonction/pronom
    # relatif ("(autre que le Cédant)") : fait partie de la phrase, pas un
    # blanc à remplir (trouvé sur l'Article 3).
    if any(mot in ("que", "qui", "dont") for mot in mots):
        return False
    return True


def valider_article(entry: dict) -> list[str]:
    """Retourne la liste des erreurs trouvées pour cet article (vide = OK)."""
    erreurs = []
    texte = entry["texte"]
    variables = entry.get("variables", [])

    if entry.get("cible") == "clause" and not (entry.get("description") or "").strip():
        # description_clause sert au matching sémantique de l'intention
        # utilisateur (recherche par embeddings côté copilot) -- distincte de
        # titre_clause par construction (voir description_clause dans
        # contract_clause_library.py). Erreur bloquante plutôt qu'un fallback
        # silencieux sur le titre : un fallback aurait juste reproduit le bug
        # historique (description == titre pour les 61 clauses v2).
        erreurs.append("champ \"description\" manquant ou vide (requis pour toute clause)")

    libelles_declares = {v["libelle"] for v in variables}
    for v in variables:
        if v.get("depend_de_variable"):
            # Variable "composition" (ex. article 7.5, `seuil_pourcentage`
            # dépendant de `regle_distribution`) : n'apparaît jamais comme un
            # placeholder littéral à elle seule dans le texte -- elle est
            # injectée par `valeurs_par_choix` DANS le gabarit de la variable
            # dont elle dépend (voir `_render_clause_texte`, service). Pas la
            # même chose qu'une variable "déclarée mais absente" -- exclue de
            # ce contrôle, volontairement.
            continue
        occurrences = texte.count(f"({v['libelle']})")
        # Réutilisation intentionnelle du même placeholder à plusieurs endroits
        # du texte (ex. article 2, cas 15/16 et 20/24 du triage : deux blancs
        # Bpifrance qui désignent en réalité la même valeur négociée) -- doit
        # être déclarée explicitement via `occurrences_attendues` sur la
        # variable, sinon >1 reste traité comme une ambiguïté (le bug trouvé et
        # corrigé à la main sur le Préambule). `_render_clause_texte` (service)
        # remplace déjà TOUTES les occurrences d'un placeholder (str.replace),
        # donc la réutilisation fonctionne au rendu sans changement côté runtime.
        attendues = v.get("occurrences_attendues", 1)
        if occurrences == 0:
            erreurs.append(f"variable '{v['nom']}' (libellé \"{v['libelle']}\") déclarée mais absente du texte")
        elif occurrences != attendues:
            erreurs.append(
                f"placeholder \"({v['libelle']})\" apparaît {occurrences} fois dans le texte "
                f"(attendu : {attendues}) -- ambigu si non intentionnel, sinon déclarer "
                f"\"occurrences_attendues\": {occurrences} sur la variable"
            )

    for match in PLACEHOLDER_RE.finditer(texte):
        contenu = match.group(1)
        if contenu not in libelles_declares and _ressemble_a_un_placeholder(contenu):
            erreurs.append(
                f"placeholder \"({contenu})\" ressemble à un blanc à remplir mais aucune variable ne le déclare"
            )

    return erreurs


def _conditions(entry: dict) -> dict:
    conditions = entry.get("conditions_affichage") or {}
    return {
        "formes_juridiques_concernees": conditions.get("formes_juridiques_concernees"),
        "necessite_investisseurs": conditions.get("necessite_investisseurs", False),
        "necessite_absence_investisseurs": conditions.get("necessite_absence_investisseurs", False),
        "depend_de_section": conditions.get("depend_de_section"),
        "depend_de_variantes": conditions.get("depend_de_variantes"),
    }


def main() -> None:
    with DECISIONS.open(encoding="utf-8") as f:
        decisions = json.load(f)

    titres_articles = decisions.get("titres_articles", {})

    clauses = []
    templates = []
    validity_criteria = []
    groupes_variantes = {}  # groupe_section -> {ordre, titre_affiche, explication, candidats, conditions}
    toutes_erreurs = {}
    articles_avec_titre_emis = set()

    for ordre, entry in enumerate(decisions["articles"], start=1):
        # Titre d'article (Article 1 - Objet..., Article 2 - Cessions...) :
        # injecté une seule fois, juste avant la 1ère entrée de cet article,
        # qu'elle soit traitée ou non plus bas -- sinon un article dont la
        # 1ère entrée est encore "a_traiter_plus_tard" perdrait son titre.
        # Réutilise "texte_statique" (déjà géré tel quel par
        # `_assemble_document_text` côté service) plutôt qu'un nouveau
        # comportement_section : rien à changer côté service.
        #
        # `texte_statique: None` (pas `titre_info["texte"]`) : ce bloc n'est
        # QU'un titre de chapitre (signet PDF), pas un paragraphe de corps --
        # le dupliquer dans `texte_statique` faisait réafficher le même texte
        # deux fois à la suite dans le PDF (une fois en titre, une fois en
        # corps de texte italique). Bug trouvé le 24/09/2026 sur le rendu
        # généré. `render_document_as_pdf` sait désormais poser un signet/titre
        # même sans corps (voir pdf_rendering_service.py) -- ce bloc ne perd
        # rien en passant `texte_statique` à None.
        cle_article = str(entry["article"])
        titre_info = titres_articles.get(cle_article)
        if titre_info and cle_article not in articles_avec_titre_emis:
            templates.append({
                "code_section": f"titre_article_{cle_article}",
                "article": entry["article"],
                "comportement_section": "texte_statique",
                "obligatoire": True,
                "ordre": ordre - 0.5,
                "titre_affiche": titre_info["texte"],
                "explication": None,
                "texte_statique": None,
                **_conditions({}),
            })
            articles_avec_titre_emis.add(cle_article)

        if entry["cible"] in ("a_traiter_plus_tard", "donnee_projet_dynamique"):
            # Rien à générer dans les fichiers _v2 par ce script : soit la
            # décision de contenu n'est pas encore prise ("a_traiter_plus_tard"),
            # soit le contenu dépend d'une liste d'associés connue seulement à
            # l'exécution ("donnee_projet_dynamique", ex. "entete") -- ce
            # générateur ne produit que des clauses/textes fixes. L'article
            # reste tracé dans decisions_articles.json (pas un trou silencieux),
            # juste pas dans ces fichiers de sortie.
            continue

        erreurs = valider_article(entry)
        if erreurs:
            toutes_erreurs[entry["code"]] = erreurs
            continue

        comportement = entry.get("comportement_section", "mention_obligatoire")

        if entry["cible"] == "clause":
            clauses.append({
                "code_clause": entry["code"],
                "article": entry["article"],
                "titre_clause": entry["titre"],
                "description_clause": entry["description"],
                "texte_clause": entry["texte"],
                "variables_requises": entry.get("variables", []),
                "sous_variantes_candidates": None,
            })

            for critere in entry.get("validity_criteria", []):
                validity_criteria.append({**critere, "code_clause": entry["code"]})

            if comportement == "mention_obligatoire":
                templates.append({
                    "code_section": entry["code"],
                    "article": entry["article"],
                    "comportement_section": "mention_obligatoire",
                    "obligatoire": True,
                    "ordre": ordre,
                    "titre_affiche": entry["titre"],
                    "explication": None,
                    "reference_code_clause": entry["code"],
                    **_conditions(entry),
                })
            elif comportement == "clause_optionnelle":
                templates.append({
                    "code_section": entry["code"],
                    "article": entry["article"],
                    "comportement_section": "clause_optionnelle",
                    "obligatoire": False,
                    "ordre": ordre,
                    "titre_affiche": entry["titre"],
                    "explication": entry.get("explication"),
                    "reference_code_clause": entry["code"],
                    **_conditions(entry),
                })
            elif comportement == "variante_obligatoire":
                groupe_code = entry["groupe_section"]
                g = groupes_variantes.setdefault(groupe_code, {
                    "ordre": ordre,
                    "article": entry["article"],
                    "titre_affiche": None,
                    "explication": None,
                    "candidats": [],
                    "conditions": _conditions(entry),
                })
                g["candidats"].append(entry["code"])
                if entry.get("titre_section"):
                    g["titre_affiche"] = entry["titre_section"]
                if entry.get("explication_section"):
                    g["explication"] = entry["explication_section"]
            else:
                toutes_erreurs[entry["code"]] = [f"comportement_section inconnu : '{comportement}'"]
        elif entry["cible"] == "texte_statique":
            templates.append({
                "code_section": entry["code"],
                "article": entry["article"],
                "comportement_section": "texte_statique",
                "obligatoire": True,
                "ordre": ordre,
                "titre_affiche": entry["titre"],
                "explication": None,
                "texte_statique": entry["texte"],
                **_conditions(entry),
            })
        else:
            toutes_erreurs[entry["code"]] = [f"cible inconnue : '{entry['cible']}'"]

    for groupe_code, g in groupes_variantes.items():
        templates.append({
            "code_section": groupe_code,
            "article": g["article"],
            "comportement_section": "variante_obligatoire",
            "obligatoire": False,
            "ordre": g["ordre"],
            "titre_affiche": g["titre_affiche"],
            "explication": g["explication"],
            "reference_code_clause": None,
            "variantes_candidates": g["candidats"],
            **{k: v for k, v in g["conditions"].items()},
        })

    if toutes_erreurs:
        print("ÉCHEC -- erreurs trouvées, rien n'est écrit :")
        for code, errs in toutes_erreurs.items():
            print(f"  [{code}]")
            for e in errs:
                print(f"    - {e}")
        raise SystemExit(1)

    # Renumérotation finale : l'`ordre` brut (index d'énumération sur TOUTES les
    # entrées de decisions_articles.json) laisse des trous -- une entrée
    # "a_traiter_plus_tard"/"donnee_projet_dynamique" consomme un numéro sans
    # jamais être émise, et plusieurs entrées "variante_obligatoire" d'un même
    # groupe consomment chacune un numéro alors qu'une seule section est
    # produite pour tout le groupe (trouvé sur l'Article 2 : "inalienabilite"
    # regroupe 4 entrées mais n'émet qu'1 section -- ordre passait de 12 à 14).
    # Le tri relatif reste correct (basé sur l'ordre brut, qui suit l'ordre du
    # document) -- on renumérote juste en 1..N sans trou pour que le fichier
    # de sortie soit lisible tel quel.
    templates.sort(key=lambda t: t["ordre"])
    for nouvel_ordre, t in enumerate(templates, start=1):
        t["ordre"] = nouvel_ordre

    CLAUSES_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CLAUSES_OUT.open("w", encoding="utf-8") as f:
        json.dump(clauses, f, ensure_ascii=False, indent=2)
    with TEMPLATES_OUT.open("w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    with VALIDITY_OUT.open("w", encoding="utf-8") as f:
        json.dump(validity_criteria, f, ensure_ascii=False, indent=2)

    print(f"OK -- {len(clauses)} clause(s), {len(templates)} section(s) de squelette, {len(validity_criteria)} critère(s) de validité générés.")
    for t in templates:
        print(f"  - {t['code_section']} ({t['comportement_section']})")


if __name__ == "__main__":
    main()
