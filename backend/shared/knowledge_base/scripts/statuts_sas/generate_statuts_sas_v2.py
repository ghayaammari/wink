"""Script générateur des fichiers finaux statuts SAS (service 1.1.4, Phase 4,
22/09/2026) : produit `statuts_sas_clauses.json`,
`statuts_sas_document_templates.json` et `statuts_sas_validity_criteria.json`
à partir de `decisions_articles_statuts_sas.json`, au lieu qu'ils soient tapés
à la main dans leur format final.

Même principe que `generate_pacte_fondateurs_v2.py` (dont ce script est
dérivé) : `decisions_articles_statuts_sas.json` reste un format court,
lisible, où chaque entrée = une décision de contenu (texte nettoyé +
variables) ; ce script fait le travail mécanique répétitif (structure des
3 fichiers de sortie, vérifications) qu'un humain peut oublier de refaire à
chaque entrée.

Adaptations par rapport au générateur pacte (différences réelles des données
statuts SAS, pas des choix arbitraires) :

1. `choix_possibles` -> `options` (variables `type='choix'`). Le clausier
   déclare la liste fermée sous `choix_possibles` ; le moteur
   (`_validate_variables`, document_generation_service.py) valide les choix
   contre `v.get("options", [])`. Le mapping se fait ICI (assemblage
   mécanique), jamais dans le clausier -- le clausier garde son champ
   sémantique, le fichier final porte le champ lu par le moteur.

2. Sections "chapeau" ignorées. 9 entrées du clausier (capital_social,
   avantages_particuliers, transmission_actions, location_actions,
   commissaires_aux_comptes, exercice_social, nomination_premier_president,
   nomination_premier_directeur_general, nomination_premiers_membres_comite)
   sont des têtes d'article dont le texte est un simple marqueur entre
   parenthèses ("(variantes ci-dessous)", "(texte choisi parmi les variantes
   ci-dessous)", "(texte de capital social choisi parmi les variantes
   ci-dessous)") et qui ne portent AUCUNE variable : leur contenu est
   entièrement porté par les variantes du groupe qui suit. Les émettre comme
   clauses produirait une clause au texte absurde ET -- pour 8 d'entre elles
   -- une collision de `code_section` avec le template `variante_obligatoire`
   du groupe du même nom (ex. `commissaires_aux_comptes` chapeau + groupe).
   Détection : cible "clause", aucune variable, texte qui EST un marqueur
   entre parenthèses (`texte.strip()` commence par "(" et finit par ")").
   Elles restent tracées dans decisions_articles_statuts_sas.json (pas un
   trou silencieux) ; ce script les ignore avec un message en sortie.

3. `necessite_investisseurs` / `necessite_absence_investisseurs` normalisées
   `None` -> `false` : les entrées SAS portent `null` dans
   `conditions_affichage` (champ toujours inapplicable pour les statuts, pas
   de notion d'associés investisseurs comme au pacte), mais les colonnes DB
   sont `NOT NULL server_default false` -- le fichier final doit donc porter
   un booléen, pas `null` (`_conditions` du générateur pacte recopierait le
   `null` tel quel).

Le reste suit exactement le générateur pacte : comportements par entrée
(mention_obligatoire / clause_optionnelle / variante_obligatoire / défaut
mention_obligatoire), groupes de variantes via `groupe_section` +
`titre_section`/`explication_section`, titres d'articles injectés comme blocs
`texte_statique`, `code_clause` ajouté automatiquement aux `validity_criteria`,
vérifications bloquantes (description requise pour toute clause ; chaque
`libelle` de variable présent EXACTEMENT une fois dans le texte de son
entrée, sauf variables `depend_de_variable` ; tout "(...)" restant qui
ressemble à un blanc à remplir mais n'est déclaré par aucune variable).

Vérifications de cohérence supplémentaires propres aux statuts SAS :
  - chaque `resout_depuis_section` (variables `reference_croisee`) doit
    pointer vers un `code` d'entrée OU un `groupe_section` existant du
    clausier (sinon la référence croisée serait morte au moment du rendu) ;
  - `code_section` unique (les chapeaux ignorés ne doivent pas laisser de
    doublon avec leur groupe).

Non traité ici (Phase 6, test moteur) : les types de variables propres aux
statuts (`auto_*_associe`, `auto_identite_associe`, `auto_montant_*`,
`auto_representant_*`, ...) et la résolution de `resout_depuis_section` vers
le numéro d'article final -- le moteur document_generation_service.py sera
étendu pour les lire ; ce script se contente de les préserver tels quels dans
`variables_requises`.

Sortie :
  - `backend/entrepreneur/scripts/data/statuts_sas_clauses.json`
  - `backend/entrepreneur/scripts/data/statuts_sas_document_templates.json`
  - `backend/entrepreneur/scripts/data/statuts_sas_validity_criteria.json`

Lancement : `python -m backend.shared.knowledge_base.scripts.statuts_sas.generate_statuts_sas_v2`
depuis `wink/`.
"""
import json
import re
from pathlib import Path

DECISIONS = Path("backend/shared/knowledge_base/scripts/data/statuts_sas_raw/decisions_articles_statuts_sas.json")
CLAUSES_OUT = Path("backend/entrepreneur/scripts/data/statuts_sas_clauses.json")
TEMPLATES_OUT = Path("backend/entrepreneur/scripts/data/statuts_sas_document_templates.json")
VALIDITY_OUT = Path("backend/entrepreneur/scripts/data/statuts_sas_validity_criteria.json")

PLACEHOLDER_RE = re.compile(r"\(([^()]+)\)")

# Marqueurs d'énumération juridique standards ("(i)", "(ii)", ...) : ressemblent
# à un placeholder court (<=4 mots, pas de " ou ") mais n'en sont pas -- même
# liste que le générateur pacte (voir son docstring).
MARQUEURS_ENUMERATION = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def _ressemble_a_un_placeholder(contenu: str) -> bool:
    """Même filtre que `classify()` dans `extract_pacte_fondateurs_variables.py`
    (NON_VARIABLE / A_CONFIRMER) et que le générateur pacte -- un vrai
    placeholder est un groupe nominal court (<=4 mots), sans " ou " ni
    parenthèse imbriquée. Reprend les exclusions de la version pacte et
    ajoute les parenthèses légales propres au modèle SAS (inventions de la
    rédaction Bpifrance, jamais des blancs à remplir) : fractions ("(1/3)"),
    ordinaux français ("(2e)", "(10e)", "(1er)"), pourcentages ("(10 %)") et
    renvois d'annexes ("(Annexe I)"). Voir le docstring de la version pacte
    pour les cas communs (énumérations "(i)", "(ci-après désignée la
    « Société »)", "trente (30) jours", ...).
    """
    t = contenu.strip()
    tl = t.lower()
    if tl in MARQUEURS_ENUMERATION:
        return False
    if "(" in t:
        return False
    # Marqueurs d'accord grammatical français ("Titre(s)", "au(x)") : une seule
    # lettre entre parenthèses, jamais un vrai placeholder.
    if len(t) <= 1:
        return False
    if tl.startswith("clause de ") or tl.startswith("clause d'"):
        return False
    if re.match(r"^(le |la |les |l['’])?«.*»$", t):
        return False
    if t.isdigit():
        return False
    # Parenthèses légales du modèle SAS : fraction ("1/3"), ordinal français
    # ("2e", "10e", "1er"), pourcentage ("10 %", "10%"), renvoi d'annexe.
    if "/" in t:
        return False
    if re.fullmatch(r"\d+(er|re|e|eme|ème)", tl):
        return False
    if re.fullmatch(r"\d+([.,]\d+)?\s?%", t):
        return False
    if tl.startswith("annexe "):
        return False
    mots = tl.split()
    if len(mots) > 4 or " ou " in tl or tl.startswith("ou ") or tl.startswith("et "):
        return False
    if any(mot in ("que", "qui", "dont") for mot in mots):
        return False
    return True


def _est_chapeau(entry: dict) -> bool:
    """Section "chapeau" : cible clause, aucune variable, texte = marqueur entre
    parenthèses -- sa tête d'article n'a pas de contenu propre, tout est porté
    par les variantes du groupe qui suit. Voir docstring de module (point 2).
    """
    if entry.get("cible") != "clause":
        return False
    if entry.get("variables"):
        return False
    texte = (entry.get("texte") or "").strip()
    return texte.startswith("(") and texte.endswith(")")


def _variable_sortie(v: dict, articles_par_section: dict | None = None) -> dict:
    """Variable telle qu'émise dans `variables_requises` : mapping mécanique
    `choix_possibles` -> `options` (voir docstring de module, point 1). Tous
    les autres champs (`libelle`, `champ`, `selection`, `resout_depuis_section`,
    `depend_de_variable`/`depend_de_valeurs`, `commentaire`) sont préservés tels
    quels.

    AJOUT (24/09/2026, audit #13) : pour une `reference_croisee` portant
    `resout_depuis_section`, écrit `article_cible` = numéro d'article de la
    section visée. Le moteur n'avait AUCUN moyen de connaître ce numéro
    (`document_templates` n'a pas de colonne `article`) : les 17 renvois
    sortaient vides dans le PDF. Calculé ici plutôt qu'en base (pas de
    migration) : le générateur est déjà la source de vérité de la
    numérotation ; si elle change, une régénération suffit. Lu au rendu par
    `statuts_sas_resolvers._resoudre_references_articles`.
    """
    sortie = dict(v)
    if "choix_possibles" in sortie:
        sortie["options"] = sortie.pop("choix_possibles")
    rds = sortie.get("resout_depuis_section")
    if sortie.get("type") == "reference_croisee" and rds and articles_par_section:
        if rds in articles_par_section:
            sortie["article_cible"] = articles_par_section[rds]
    return sortie


# Garde-fou (lot 3, 24/09/2026) : variables dont la valeur EXISTE déjà dans
# les données du projet (profil juridique, associés) -- jamais une saisie
# libre dans les statuts. Trou constaté : `sigle`, `objectifs_ess`,
# `designation_bien_apporte`... déclarées "texte" alors que la colonne
# existait, donc redemandées à l'utilisateur (et parfois IGNORÉES au rendu).
# Clé = (code_clause, nom de variable), valeur = types acceptés. Une nouvelle
# clause qui réutilise une de ces données : l'ajouter ici.
VARIABLES_DONNEES_PROJET: dict[tuple[str, str], set[str]] = {
    ("objet_social", "activites_societe"): {"auto_profil_juridique"},
    ("raison_d_etre", "raison_d_etre"): {"auto_profil_juridique"},
    ("economie_sociale_solidaire", "objectifs_ess"): {"auto_profil_juridique"},
    ("sigle", "sigle"): {"auto_profil_juridique"},
    ("capital_actions_ordinaires", "valeur_nominale"): {"auto_profil_juridique"},
    # Lot A : « intégralement / partiellement libérées » se DÉDUIT de la
    # variante choisie à l'Art. 6 -- jamais une 2e question qui pourrait la
    # contredire.
    ("capital_actions_ordinaires", "liberation_actions"): {"reference_croisee"},
    # Lieu/date de signature : volontairement SAISIS (décision utilisateur
    # 24/09/2026 -- ils changent à chaque génération), donc absents d'ici.
    ("cloture_fait_a_signature", "signatures_associes"): {"auto_signatures_associes"},
    **{("apport_numeraire_liberes", n): {"auto_apport_par_associe"} for n in ("somme", "nombre_actions", "valeur_nominale")},
    **{
        ("apport_numeraire_non_liberes", n): {"auto_apport_par_associe"}
        for n in ("somme_total", "somme_libérée", "nombre_actions", "valeur_nominale")
    },
    ("apport_nature_identite", "designation_bien_apporte"): {"auto_apport_par_associe"},
    **{
        ("dispense_commissaire_apports_l225_8_1", n): {"auto_apport_par_associe"}
        for n in ("nature_biens", "somme_apport_nature", "nombre_actions", "valeur_nominale")
    },
    ("apports_industrie", "prestations_industrie"): {"texte_par_associe"},
    **{("apports_industrie", n): {"nombre_par_associe"} for n in ("nombre_actions", "pourcentage_benefices", "pourcentage_pertes")},
}


SOUS_NUMERO_EN_DUR_RE = re.compile(r"^\s*\d+\.\d+(\s|\.|\s*bis)")
ARTICLE_EN_DUR_RE = re.compile(r"^\s*Article\s+\d+\s*-", re.IGNORECASE)


MODES_ARTICLE_ABSENT = frozenset({"cible_obligatoire", "texte", "liaison", "aucune"})


def valider_article(entry: dict) -> list[str]:
    """Retourne la liste des erreurs trouvées pour cette entrée (vide = OK).
    Même contrat que le générateur pacte (description requise, chaque blanc
    exactement une fois dans le texte, aucun "(...)" ressemblant à un blanc non
    déclaré), avec une différence de convention : dans le clausier statuts SAS
    le texte porte `(nom)` de variable (ex. "(capital_social)"), pas le
    `libelle` ("montant du capital social" reste le libellé humain). Le
    contrôle d'occurrence et le contrôle des placeholders non déclarés se font
    donc sur les `nom`.
    """
    erreurs = []
    texte = entry["texte"]
    variables = entry.get("variables", [])

    if not (entry.get("description") or "").strip():
        erreurs.append("champ \"description\" manquant ou vide (requis pour toute clause)")

    noms_declares = {v["nom"] for v in variables}
    for v in variables:
        if v.get("depend_de_variable"):
            # Variable dépendante (ex. `majorite_renforcee` injectée dans la
            # variante "la majorité renforcée des X %") : injectée dans la
            # valeur de la variable parente, jamais comme placeholder autonome
            # -- exclue du contrôle, comme dans le générateur pacte.
            continue
        occurrences = texte.count(f"({v['nom']})")
        attendues = v.get("occurrences_attendues", 1)
        if occurrences == 0:
            erreurs.append(f"variable '{v['nom']}' déclarée mais absente du texte")
        elif occurrences != attendues:
            erreurs.append(
                f"placeholder \"({v['nom']})\" apparaît {occurrences} fois dans le texte "
                f"(attendu : {attendues}) -- ambigu si non intentionnel, sinon déclarer "
                f"\"occurrences_attendues\": {occurrences} sur la variable"
            )

    # Garde-fou numérotation (lot A, 24/09/2026) : les numéros d'article et
    # de sous-section sont calculés AU RENDU sur les articles réellement
    # présents -- jamais écrits dans le texte (trous et doublons constatés
    # sur un PDF réel : « 6.1 » imprimé 2 fois, « Article 11 » après
    # « Article 7 »). Un sous-titre s'écrit « § Titre » en début de ligne.
    for ligne in texte.splitlines():
        if SOUS_NUMERO_EN_DUR_RE.match(ligne):
            erreurs.append(
                f"sous-numéro écrit en dur : « {ligne.strip()[:40]} » -- écrire « § Titre » (numéroté au rendu)"
            )
        if ARTICLE_EN_DUR_RE.match(ligne):
            erreurs.append(f"titre d'article écrit en dur dans le texte : « {ligne.strip()[:40]} »")

    # Niveau B (24/09/2026) : le contrôle juridique LLM ne porte que sur du
    # texte libre -- un nombre, une date ou un choix se vérifient par code.
    for v in variables:
        if v.get("controle_juridique") and v.get("type") not in ("texte", "texte_par_associe"):
            erreurs.append(f"variable '{v['nom']}' : controle_juridique réservé aux types texte (type : {v.get('type')})")

    # Renvois d'article (25/09/2026) : chaque renvoi dit comment la
    # vérification finale (tool `correction_renvois`) corrige le texte si
    # l'article visé n'est pas dans les statuts. Jamais de suppression de
    # clause ni d'article (décision utilisateur).
    #   cible_obligatoire : l'article visé est toujours présent (vérifié plus bas) ;
    #   texte             : `remplace` (présent tel quel dans le texte, contient
    #                       le placeholder) est remplacé par `par` (texte relu) ;
    #   liaison           : placeholder de liaison, toujours rendu vide ;
    #   aucune            : pas de correction possible, texte laissé tel quel
    #                       (en pratique la clause est déjà écartée du parcours).
    for v in variables:
        if v.get("type") != "reference_croisee" or not v.get("resout_depuis_section"):
            continue
        regle = v.get("si_article_absent")
        mode = (regle or {}).get("mode")
        if mode not in MODES_ARTICLE_ABSENT:
            erreurs.append(
                f"renvoi '{v['nom']}' sans `si_article_absent` valide (modes : {', '.join(sorted(MODES_ARTICLE_ABSENT))})"
            )
        elif mode == "texte":
            remplace = regle.get("remplace") or ""
            if f"({v['nom']})" not in remplace or remplace not in texte or "par" not in regle:
                erreurs.append(
                    f"renvoi '{v['nom']}' : `remplace` doit figurer tel quel dans le texte et contenir le placeholder, `par` est requis"
                )

    # Pas de double contrôle (24/09/2026) : un champ vérifié par code (cible
    # d'un critère `valeur_limite`) n'est jamais aussi envoyé au LLM -- sinon
    # deux verdicts, potentiellement contradictoires, sur la même valeur.
    cibles_code = set()
    for critere in entry.get("validity_criteria", []):
        limite = critere.get("valeur_limite") or {}
        cibles_code |= {limite.get("variable"), limite.get("jour_variable"), limite.get("mois_variable")}
        cibles_code |= set(limite.get("variables") or [])
    for v in variables:
        if v.get("controle_juridique") and v["nom"] in cibles_code:
            erreurs.append(
                f"variable '{v['nom']}' : à la fois vérifiée par code (critère) et marquée controle_juridique -- choisir un seul contrôle"
            )

    for v in variables:
        attendus = VARIABLES_DONNEES_PROJET.get((entry.get("code"), v["nom"]))
        if attendus and v.get("type") not in attendus:
            erreurs.append(
                f"variable '{v['nom']}' déclarée '{v.get('type')}' alors que sa valeur vient des données du "
                f"projet (type attendu : {' ou '.join(sorted(attendus))}) -- voir VARIABLES_DONNEES_PROJET"
            )

    for match in PLACEHOLDER_RE.finditer(texte):
        contenu = match.group(1)
        if contenu not in noms_declares and _ressemble_a_un_placeholder(contenu):
            erreurs.append(
                f"placeholder \"({contenu})\" ressemble à un blanc à remplir mais aucune variable ne le déclare"
            )

    return erreurs


def _conditions(entry: dict) -> dict:
    conditions = entry.get("conditions_affichage") or {}
    return {
        "formes_juridiques_concernees": conditions.get("formes_juridiques_concernees"),
        "necessite_investisseurs": bool(conditions.get("necessite_investisseurs")),
        "necessite_absence_investisseurs": bool(conditions.get("necessite_absence_investisseurs")),
        "depend_de_section": conditions.get("depend_de_section"),
        "depend_de_variantes": conditions.get("depend_de_variantes"),
    }


# -- Projection des conditions d'affichage (référentiel clausier -> moteur) --
#
# Le clausier exprime `depend_de_section`/`depend_de_variantes` dans son propre
# référentiel : codes de chapeaux (non émis), noms de groupes, marqueurs de
# présence ("clause_agrement", "actions_preference_presentes"...). Le moteur
# (l.169-172 de document_generation_service.py) n'accepte QUE :
#   - `depend_de_section` = code_section réellement émis (et déjà répondue,
#     donc antérieure dans `ordre`) ;
#   - `depend_de_variantes` = liste de `code_clause`.
# Toute dépendance non projetée rendrait la section définitivement inapplicable
# (code_clause jamais dans la liste). La projection suivante traduit donc le
# référentiel clausier vers le référentiel moteur.

# Correction #2 (audit du 23/09/2026) : groupes de variantes qui ne doivent
# JAMAIS être skippables, contrairement à la règle générale ci-dessous
# (`obligatoire: False` pour tout groupe `variante_obligatoire`). Un exercice
# social existe toujours (Art. 30, groupe `exercice_social`) : ce n'est pas
# une clause de protection qu'on peut sauter, contrairement par exemple au
# mode de transfert de siège (Art. 4, resté skippable à raison). Référentiel
# explicite, pas un cas particulier caché dans la boucle de génération --
# ajouter un `groupe_code` ici suffit pour un futur besoin similaire.
# AJOUT (24/09/2026, audit #17) : `agrement_suite` (Art. 17 §3) -- sans lui,
# une clause d'agrément ne dit pas quand le transfert agréé peut avoir lieu.
# Sa variante n'est de toute façon plus choisie par l'utilisateur : elle est
# déduite de la présence de l'Art. 16 (voir SECTIONS_DERIVEES,
# statuts_sas_resolvers.py).
GROUPES_NON_SKIPPABLES = {"exercice_social", "agrement_suite"}

# Décision utilisateur (24/09/2026) : les 17 articles classés HORS PÉRIMÈTRE
# (voir recap-service-1.1.4-statuts-sas.md, classification) sont exclus
# DÉFINITIVEMENT des statuts générés : ni titre, ni texte, ni question. Ils
# restent dans `decisions_articles_statuts_sas.json` (traçabilité, retour
# arrière possible en retirant un numéro d'ici). Vérifié avant exclusion :
# aucun renvoi (`resout_depuis_section`), aucune condition
# (`depend_de_section`) ni aucun numéro écrit en dur dans les articles gardés
# ne pointe vers eux ; les annexes elles-mêmes vivent dans le bloc de clôture
# (gardé), seule la liste des annexes (Art. 46) disparaît.
ARTICLES_HORS_PERIMETRE = {9, 10, 12, 13, 25, 26, 29, 31, 33, 34, 35, 36, 37, 38, 42, 45, 46}

# Marqueurs de présence dont la clause est une mention obligatoire du modèle
# (article toujours présent) : la condition est toujours vraie -> on neutralise.
#
# CORRECTION #18 (audit du 24/09/2026) : `clause_agrement`, `clause_preemption`
# et `clause_exclusion_ou_changement_controle` ont été RETIRÉS d'ici -- depuis
# la correction #1, les Art. 16/19/20 sont facultatifs et l'Art. 17 est
# conditionnel : ces marqueurs ne sont plus jamais "toujours vrais". Les
# neutraliser effaçait le lien (ex. ligne "comité de direction" de l'Art. 27
# proposée sans Art. 24). Ils sont maintenant projetés vers l'article réel
# (PROJECTIONS_PRESENCE ci-dessous). Restent ici les 2 marqueurs DOUBLES, que
# `depend_de_section` (une seule dépendance) ne sait pas exprimer : dette
# assumée, à traiter lors de l'audit des Art. 16/20 via SECTIONS_DERIVEES.
MARQUEURS_TOUJOURS_VRAIS = {
    "clause_preemption_ou_agrement",
    "clause_preemption_et_agrement",
}

# Marqueurs de présence projetés vers le groupe moteur qui les matérialise.
PROJECTIONS_PRESENCE = {
    "actions_preference_presentes": ("composition_capital", ["capital_actions_preference"]),
    "presence_actions_preference": ("composition_capital", ["capital_actions_preference"]),
    "designation_commissaire_apports": (
        "evaluation_apports_nature",
        ["commissaire_apports_unanimite", "commissaire_apports_ordonnance"],
    ),
    "dispense_commissaire_apports": (
        "evaluation_apports_nature",
        ["dispense_commissaire_apports_l227_1", "dispense_commissaire_apports_l225_8_1"],
    ),
    "apports_numeraire_liberation": (
        "apports_numeraire_liberation",
        ["apport_numeraire_liberes", "apport_numeraire_non_liberes"],
    ),
    # Correction #18 (24/09/2026) : marqueurs de présence d'un article
    # facultatif/conditionnel -> la clause de base de cet article.
    "clause_preemption": ("droit_preemption", ["droit_preemption"]),
    "clause_agrement": ("agrement", ["agrement"]),
    "clause_exclusion_ou_changement_controle": ("exclusion", ["exclusion"]),
}

# Sous-groupes optionnels dont le clausier ne renseigne pas le lien (dds pointe
# la mention de l'article, pas la clause porteuse des variantes) : remis
# explicitement sur la clause optionnelle parente.
SOUS_GROUPES_OPTIONNELS = {
    "motifs_revocation_president": "revocation_president_justes_motifs",
}


def _projeter_conditions_affichage(templates: list) -> None:
    """Projette `depend_de_section`/`depend_de_variantes` de chaque template du
    référentiel clausier vers le référentiel moteur (voir commentaire ci-dessus).
    Modifie les templates en place ; trace chaque décision sur stdout."""
    par_code = {t["code_section"]: t for t in templates}
    candidats_par_groupe = {
        t["code_section"]: t.get("variantes_candidates") or []
        for t in templates
        if t["comportement_section"] == "variante_obligatoire"
    }

    def groupe_contenant(code_clause: str) -> str | None:
        """Le(s) groupe(s) dont le code_clause est un candidat. Ambigu si
        plusieurs groupes partagent un candidat -- non le cas aujourd'hui."""
        trouves = [g for g, cands in candidats_par_groupe.items() if code_clause in cands]
        return trouves[0] if len(trouves) == 1 else None

    def neutralise(t: dict, raison: str) -> None:
        print(f"  (conditions) {t['code_section']}: depend_de_section neutralisée — {raison}")
        t["depend_de_section"] = None
        t["depend_de_variantes"] = None

    for t in templates:
        dds = t.get("depend_de_section")
        if not dds:
            continue
        ddv = t.get("depend_de_variantes")
        ddv_list = [ddv] if isinstance(ddv, str) else (ddv or [])

        # 1. Sous-groupes optionnels déclarés (table explicite) : le dds du
        #    clausier pointe la mention de l'article, pas la clause.
        if t["code_section"] in SOUS_GROUPES_OPTIONNELS:
            parent = SOUS_GROUPES_OPTIONNELS[t["code_section"]]
            print(f"  (conditions) {t['code_section']}: sous-groupe optionnel du parent {parent}")
            t["depend_de_section"] = parent
            t["depend_de_variantes"] = [parent]
            continue

        # 2. dds = chapeau ignoré / section jamais émise.
        if dds not in par_code:
            if len(ddv_list) == 1:
                groupe = groupe_contenant(ddv_list[0])
                if groupe:
                    print(f"  (conditions) {t['code_section']}: dds '{dds}' (chapeau) -> groupe {groupe}")
                    t["depend_de_section"] = groupe
                    t["depend_de_variantes"] = ddv_list
                    continue
                proj = PROJECTIONS_PRESENCE.get(ddv_list[0])
                if proj:
                    print(f"  (conditions) {t['code_section']}: marqueur '{ddv_list[0]}' -> {proj[0]}")
                    t["depend_de_section"], t["depend_de_variantes"] = proj[0], list(proj[1])
                    continue
            neutralise(t, f"dds '{dds}' non émis (chapeau ignoré), ddv={ddv}")
            continue

        # 3. ddv vide : rattachement d'article, sauf si dds est une
        #    clause_optionnelle (le groupe porte alors les variantes de la
        #    clause : il ne s'affiche que si la clause est acceptée).
        if not ddv_list:
            if par_code[dds]["comportement_section"] == "clause_optionnelle":
                t["depend_de_variantes"] = [dds]
                print(f"  (conditions) {t['code_section']}: sous-groupe optionnel du parent {dds}")
            else:
                neutralise(t, f"ddv vide : rattachement d'article '{dds}' sans condition moteur")
            continue

        # 4. Marqueurs de présence toujours vrais (clauses obligatoires).
        if any(v in MARQUEURS_TOUJOURS_VRAIS for v in ddv_list):
            neutralise(t, f"marqueur {ddv_list} toujours vrai (article mention obligatoire)")
            continue

        # 5. Marqueurs de présence projetés vers leur groupe moteur.
        proj = next((PROJECTIONS_PRESENCE[v] for v in ddv_list if v in PROJECTIONS_PRESENCE), None)
        if proj and proj[0] in par_code and par_code[proj[0]]["ordre"] >= t["ordre"]:
            # Correction #18 : la section cible est placée APRÈS (ex. clause
            # de l'Art. 16 qui dépend de l'agrément, Art. 17). Le moteur ne lit
            # que des sections déjà répondues -> condition impossible. Même
            # comportement qu'avant #18 (neutralisée), mais tracé : dette
            # assumée, à traiter lors de l'audit des Art. 16/20.
            neutralise(t, f"marqueur {ddv_list} -> '{proj[0]}' POSTÉRIEURE (dette, audit Art. 16/20)")
            continue
        if proj:
            print(f"  (conditions) {t['code_section']}: marqueur {ddv_list} -> {proj[0]}")
            t["depend_de_section"], t["depend_de_variantes"] = proj[0], list(proj[1])
            continue

        # 6. ddv = candidats réels de dds (déjà au format moteur ; on normalise
        #    en liste pour le moteur 'not in (list)').
        candidats_de_dds = par_code[dds].get("variantes_candidates") or []
        if all(v in candidats_de_dds for v in ddv_list):
            t["depend_de_variantes"] = ddv_list
            continue

        # 7. ddv = variante d'un groupe quand dds est une mention (ex. variant
        #    'rapport_gestion_si_loi' dépend du groupe rapport_gestion).
        if len(ddv_list) == 1:
            groupe = groupe_contenant(ddv_list[0])
            if groupe:
                print(f"  (conditions) {t['code_section']}: ddv '{ddv_list[0]}' -> groupe {groupe}")
                t["depend_de_section"] = groupe
                t["depend_de_variantes"] = [ddv_list[0]]
                continue

        # 8. Reste (marqueur non reconnu) : neutraliser plutôt que produire une
        #    condition qui masquerait la section définitivement.
        neutralise(t, f"ddv {ddv_list} non projetable sur cible '{dds}'")


def main() -> None:
    with DECISIONS.open(encoding="utf-8") as f:
        decisions = json.load(f)

    titres_articles = decisions.get("titres_articles", {})

    clauses = []
    templates = []
    validity_criteria = []
    groupes_variantes = {}  # groupe_section -> {ordre, article, titre_affiche, explication, candidats, conditions}
    toutes_erreurs = {}
    articles_avec_titre_emis = set()
    chapeaux_ignores = []

    # Cohérence des références croisées : un `resout_depuis_section` doit
    # pointer vers un code d'entrée ou un groupe du clausier.
    codes_entrees = {str(e["code"]) for e in decisions["articles"] if e.get("cible") == "clause"}
    groupes_reels = {e["groupe_section"] for e in decisions["articles"] if e.get("groupe_section")}
    # Audit #13 : numéro d'article de chaque code d'entrée ET de chaque groupe,
    # pour résoudre les renvois `resout_depuis_section` (voir _variable_sortie).
    articles_par_section = {str(e["code"]): e["article"] for e in decisions["articles"] if e.get("cible") == "clause"}
    articles_par_section.update(
        {e["groupe_section"]: e["article"] for e in decisions["articles"] if e.get("groupe_section")}
    )
    suppressions = 0

    exclus_hors_perimetre = 0
    for ordre, entry in enumerate(decisions["articles"], start=1):
        if entry.get("article") in ARTICLES_HORS_PERIMETRE:
            exclus_hors_perimetre += 1
            continue
        # Titre d'article (Article 1 - Forme, Article 2 - Objet, ...) : injecté
        # une seule fois, juste avant la 1ère entrée de cet article, qu'elle
        # soit traitée, ignorée ou "donnee_projet_dynamique" -- même mécanique
        # que le générateur pacte.
        cle_article = str(entry["article"])
        titre_info = titres_articles.get(cle_article)
        if titre_info and cle_article not in articles_avec_titre_emis:
            if ARTICLE_EN_DUR_RE.match(titre_info["texte"]):
                # Lot A : le titre ne porte que l'intitulé (« Forme ») -- le
                # « Article N – » est ajouté au rendu avec le numéro final.
                toutes_erreurs.setdefault(f"titre_article_{cle_article}", []).append(
                    f"titre « {titre_info['texte'][:40]} » : retirer « Article N - » (numéroté au rendu)"
                )
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
            # Rien à générer : contenu dépendant des données du projet connues
            # seulement à l'exécution ("donnee_projet_dynamique", ex. "entete"
            # / identification des parties) ou décision de contenu pas encore
            # prise. Reste tracé dans decisions_articles_statuts_sas.json.
            continue

        if _est_chapeau(entry):
            chapeaux_ignores.append(f"{entry['code']} (article {entry['article']})")
            continue

        # Variables de la forme "candidat retiré" (`code` préfixé "supprime_")
        # : conservées dans le clausier pour la traçabilité du triage, mais
        # aucune section/clause ne doit en être émise. (Aucune aujourd'hui ;
        # la règle protège des ajouts futurs.)
        if str(entry.get("code", "")).startswith("supprime_"):
            suppressions += 1
            continue

        erreurs = valider_article(entry)
        if erreurs:
            toutes_erreurs[entry["code"]] = erreurs
            continue

        # Références croisées : le `resout_depuis_section` de chaque variable
        # doit exister (code d'entrée ou groupe). Bloquant comme le reste :
        # une référence morte produirait un numéro d'article jamais résolu.
        for v in entry.get("variables", []):
            rds = v.get("resout_depuis_section")
            if rds is not None and rds not in codes_entrees and rds not in groupes_reels:
                toutes_erreurs.setdefault(entry["code"], []).append(
                    f"variable '{v['nom']}' : resout_depuis_section '{rds}' inconnu "
                    f"(ni code d'entrée ni groupe_section du clausier)"
                )
        if entry["code"] in toutes_erreurs:
            continue

        comportement = entry.get("comportement_section", "mention_obligatoire")
        variables = [_variable_sortie(v, articles_par_section) for v in entry.get("variables", [])]

        if entry["cible"] == "clause":
            clauses.append({
                "code_clause": entry["code"],
                "article": entry["article"],
                "titre_clause": entry["titre"],
                "description_clause": entry["description"],
                "texte_clause": entry["texte"],
                "variables_requises": variables,
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
            "obligatoire": groupe_code in GROUPES_NON_SKIPPABLES,
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

    # Renvois « cible_obligatoire » : l'article visé doit vraiment être une
    # section obligatoire toujours présente (sinon le mode est faux).
    obligatoires = {
        t["code_section"] for t in templates if t.get("obligatoire") and t.get("comportement_section") == "mention_obligatoire"
    }
    for c in clauses:
        for v in c["variables_requises"]:
            regle = v.get("si_article_absent") or {}
            if regle.get("mode") == "cible_obligatoire" and v.get("resout_depuis_section") not in obligatoires:
                print(f"ÉCHEC -- [{c['code_clause']}] renvoi '{v['nom']}' marqué cible_obligatoire, "
                      f"mais '{v.get('resout_depuis_section')}' n'est pas une section obligatoire")
                raise SystemExit(1)

    # Unicité des code_section (y compris groupes) -- sinon le seed échouerait.
    codes_sections = [t["code_section"] for t in templates]
    doublons = {c for c in codes_sections if codes_sections.count(c) > 1}
    if doublons:
        print(f"ÉCHEC -- code_section en doublon : {sorted(doublons)}")
        raise SystemExit(1)

    # Projection des conditions d'affichage du référentiel clausier vers le
    # référentiel moteur (depend_de_section/depend_de_variantes). À faire AVANT
    # la renumérotation : ne dépend pas de `ordre`, et les décisions sont tracées.
    print("Projection conditions_affichage (clausier -> moteur) :")
    _projeter_conditions_affichage(templates)

    # Renumérotation finale : l'`ordre` brut laisse des trous (entrées ignorées,
    # plusieurs variantes d'un même groupe). Tri relatif conservé, numéros 1..N.
    templates.sort(key=lambda t: t["ordre"])
    for nouvel_ordre, t in enumerate(templates, start=1):
        t["ordre"] = nouvel_ordre

    # Contrôle bloquant d'antériorité : le moteur (l.169-172) ne lit que des
    # sections déjà répondues, donc `depend_de_section` doit être antérieure en
    # `ordre` à la section dépendante, sinon celle-ci serait définitivement
    # inapplicable (et le seed refuserait la donnée).
    index_par_code = {t["code_section"]: t["ordre"] for t in templates}
    anterieures_invalides = [
        (t["code_section"], t["depend_de_section"])
        for t in templates
        if t.get("depend_de_section")
        and t["depend_de_section"] in index_par_code
        and index_par_code[t["depend_de_section"]] >= t["ordre"]
    ]
    if anterieures_invalides:
        print("ÉCHEC -- depend_de_section postérieure (jamais résolue par le moteur) :")
        for code, dds in anterieures_invalides:
            print(f"  {code} : depend_de_section={dds} (ordre {index_par_code[dds]} >= {index_par_code[code]})")
        raise SystemExit(1)
    dependances_restantes = sum(1 for t in templates if t.get("depend_de_section"))
    print(f"Projection terminée : {dependances_restantes} dépendance(s) moteur conservée(s).")

    CLAUSES_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CLAUSES_OUT.open("w", encoding="utf-8") as f:
        json.dump(clauses, f, ensure_ascii=False, indent=2)
    with TEMPLATES_OUT.open("w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)
    with VALIDITY_OUT.open("w", encoding="utf-8") as f:
        json.dump(validity_criteria, f, ensure_ascii=False, indent=2)

    print(f"OK -- {len(clauses)} clause(s), {len(templates)} section(s) de squelette, "
          f"{len(validity_criteria)} critère(s) de validité générés.")
    if chapeaux_ignores:
        print(f"Chapeaux ignorés ({len(chapeaux_ignores)}) : " + ", ".join(chapeaux_ignores))
    if suppressions:
        print(f"Entrées 'supprime_*' ignorées ({suppressions}) : conservées dans le clausier, non émises.")
    print(f"Articles hors périmètre exclus : {sorted(ARTICLES_HORS_PERIMETRE)} ({exclus_hors_perimetre} entrée(s) du clausier).")
    for t in templates:
        print(f"  - {t['code_section']} ({t['comportement_section']})")


if __name__ == "__main__":
    main()