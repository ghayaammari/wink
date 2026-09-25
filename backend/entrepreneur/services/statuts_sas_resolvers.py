"""Résolution des variables spécifiques au générateur de statuts SAS
(service 1.1.4) -- isolé de `document_generation_service.py` (25/09/2026) à
la demande explicite de l'utilisateur : le moteur de session/génération
(`document_generation_service.py`) reste générique et partagé avec le pacte
de fondateurs (service 1.1.13) -- voir sa docstring et
`recap-service-1.1.13-pacte-fondateurs.md` (décision déjà actée : même moteur,
`document_type` comme seul discriminant, pour éviter ~900 lignes de
duplication). Ce module-ci porte au contraire tout ce qui encode des
CONNAISSANCES MÉTIER propres au clausier statuts SAS (rôles de dirigeants,
codes de clause `apport_nature_identite`/`dispense_commissaire_apports_l225_8_1`,
formules déterministes au prorata du capital) -- rien ici n'est appelé pour
`document_type='pacte_fondateurs'`.

Frontière retenue : un mécanisme GÉNÉRIQUE, réutilisable par un futur type de
document (ex. `_variable_applicable`, `ClauseRendererBase`,
`reference_croisee`) reste dans `document_generation_service.py`/
`document_renderer_base.py`. Ce qui encode une règle SPÉCIFIQUE au clausier
statuts (un nom de clause, un rôle de dirigeant, une formule d'apport) vient
ici. Le mécanisme de sélection `auto_identite_associe`/`texte_par_associe`
ci-dessous est écrit de façon générique mais n'est aujourd'hui utilisé QUE
par le clausier statuts (vérifié 25/09/2026, aucune clause pacte n'utilise
ces types) -- il vit ici tant que ça reste vrai ; à repromouvoir dans le
moteur générique le jour où un autre type de document en aura besoin, pas
avant (éviter la généralisation prématurée).

CORRECTIF (23/09/2026) : ce module appelait `_render_clause_texte` du moteur
partagé, qui cherchait chaque placeholder par `libelle` -- correct pour le
pacte, faux pour les statuts (dont le clausier écrit `(nom)`, voir
`generate_statuts_sas_v2.py::valider_article()`), ce qui laissait 174/176
variables statuts non substituées. Corrigé en extrayant le squelette commun
dans `document_renderer_base.py` (patron Template Method) et en ajoutant
`statuts_sas_renderer.py`, dont l'instance `statuts_clause_renderer` cherche
par `nom` -- voir sa docstring. Ce module utilise maintenant
`statuts_clause_renderer.render_clause_texte(...)` partout où il appelait
`_render_clause_texte(...)` avant.

Dette technique assumée, pas cachée : `document_generation_service.py`
importe plusieurs fonctions d'ici (dans le corps de `_clause_payload`,
`_validate_variables`, `_assemble_document_blocks`, `_collect_variable_values`)
via des imports LOCAUX (à l'intérieur des fonctions), pas en tête de fichier
-- gardés tels quels par cohérence de style, même si la dépendance n'est
PLUS circulaire depuis le correctif ci-dessus (ce module n'importe plus rien
de `document_generation_service`, seulement de `document_renderer_base`/
`statuts_sas_renderer`, tous deux neutres).
"""
import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from backend.entrepreneur.models.company_officer import CompanyOfficer
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.document_renderer_base import _lit, formater_montant
from backend.entrepreneur.services.statuts_sas_renderer import statuts_clause_renderer
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary


# Rôle de gouvernance porté par chaque variable identité (art. 39/40/41,
# clauses "..._personne_physique" -- la variante "..._personne_morale" du
# même groupe_section n'a AUCUN type auto_*, saisie manuelle normale, voir
# audit du 23/09/2026). "identite" (mandataire, art. 44/clôture) diffère de
# "nom"/"adresse" (Président/DG/membre du comité) : une seule variable porte
# l'identité entière, pas de champ adresse séparé dans le texte source.
_ROLE_PAR_NOM_VARIABLE: dict[str, tuple[str, str]] = {
    "nom_complet_premier_president": ("president", "nom"),
    "adresse_premier_president": ("president", "adresse"),
    "nom_complet_premier_directeur_general": ("directeur_general", "nom"),
    "adresse_premier_directeur_general": ("directeur_general", "adresse"),
    "nom_complet_membre_comite": ("membre_comite", "nom"),
    "adresse_membre_comite": ("membre_comite", "adresse"),
    "identite_associe_mandataire": ("mandataire", "identite"),
    "identite_associe_mandataire_annexe_3": ("mandataire", "identite"),
    # AJOUT (24/09/2026, demande utilisateur) : la durée des fonctions est
    # rattachée au MANDAT (`company_officers.duree_fonctions`, voir docstring
    # du modèle), jamais à l'identité de l'associé -- donc lue directement
    # sur `CompanyOfficer`, contrairement à "nom"/"adresse"/"identite"
    # ci-dessus qui passent par `_identite_officier` (anti-redondance avec
    # `project_associates`). Variable PARTAGÉE par les 2 variantes du
    # Président (personne physique ET morale, art. 39, même nom de variable
    # dans les 2 clauses) -- une seule entrée suffit, peu importe laquelle
    # des 2 variantes est active.
    "duree_fonctions_premier_president": ("president", "duree_fonctions"),
    # AJOUT (24/09/2026, dette de l'audit #12 étendue aux Art. 40/41) : même
    # principe pour le 1er Directeur Général et les 1ers membres du comité.
    "duree_fonctions_premier_directeur_general": ("directeur_general", "duree_fonctions"),
    "duree_fonctions_membres_comite": ("membre_comite", "duree_fonctions"),
}
# Sous-ensemble ci-dessus dont la résolution donne l'identité complète en un
# seul champ (mandataire) -- exposé séparément pour _validate_variables (voir
# sa docstring : exclusion par NOM, pas par TYPE, car `auto_identite_associe`
# est partagé avec des variables non résolues ici).
_VARIABLES_MANDATAIRE = frozenset(
    nom for nom, (_, champ) in _ROLE_PAR_NOM_VARIABLE.items() if champ == "identite"
)

# Clauses dont l'identité (`auto_identite_associe`) est répétée pour TOUS les
# associés correspondant au filtre `selection`, jamais un choix parmi eux --
# voir `_render_apports_nature_statuts` (résolution Cas B, 23/09/2026, retouche
# du clausier : la clause `apport_nature_identite` a été séparée de l'en-tête
# statique "apports" précisément pour ce traitement). Distinct de
# `_VARIABLES_MANDATAIRE` (exclusion par nom de variable) : ici l'exclusion se
# fait par CLAUSE, car `identite_apporteur_nature` réapparaît ailleurs
# (`dispense_commissaire_apports_l225_8_1`) -- cette 2e clause a depuis été
# elle aussi entièrement auto-résolue (voir `_CLAUSES_ENTIEREMENT_AUTO_RESOLUES`
# ci-dessous), mais reste un ensemble séparé : `apport_nature_identite` a
# encore `designation_bien_apporte` en saisie libre (`texte_par_associe`),
# alors que `dispense_commissaire_apports_l225_8_1` n'a plus RIEN à saisir --
# les deux mécanismes de court-circuit dans `_validate_variables` sont donc
# distincts, pas redondants.
#
# AJOUT (25/09/2026, audit complet du clausier) : `apports_industrie`
# (art. 6.2 bis, `identite_apporteur_industrie`) -- même raisonnement
# qu'`apport_nature_identite`, mais AUCUN champ n'est déductible d'une
# formule ici (`prestations_industrie`/`nombre_actions`/
# `pourcentage_benefices`/`pourcentage_pertes` sont négociés au cas par cas,
# contrairement à numéraire/nature) : les 4 restent en saisie PAR ASSOCIÉ
# (`texte_par_associe`/`nombre_par_associe`, voir `_valeurs_apports_industrie_par_associe`),
# seule l'identité est répétée automatiquement ici.
_CLAUSES_REPETEES_PAR_ASSOCIE = frozenset({"apport_nature_identite", "apports_industrie"})

# Clauses dont TOUTES les variables sont désormais résolues automatiquement
# (montants déterministes + identité/désignation réutilisées) -- plus aucune
# saisie manuelle, contrairement à `_CLAUSES_REPETEES_PAR_ASSOCIE` où une
# variable (`designation_bien_apporte`) reste à saisir. Voir
# `_valeurs_dispense_l225_8_1_par_associe` et le court-circuit dans
# `_validate_variables`.
_CLAUSES_ENTIEREMENT_AUTO_RESOLUES = frozenset({"dispense_commissaire_apports_l225_8_1"})


def _identite_officier(db: Session, officer: CompanyOfficer) -> tuple[str, str | None]:
    """Retourne (identité affichable, adresse) d'UN `CompanyOfficer`.

    Anti-redondance (voir docstring du modèle) : si `associate_id` est
    renseigné, l'identité vient de `project_associates` -- source de vérité,
    jamais dupliquée sur `company_officers`. Sinon, les champs propres de la
    table sont utilisés : personne physique -- `nom_complet`/`adresse`
    (migration `acb040c7128a`, trou "Charlotte" comblé le 23/09/2026) ;
    personne morale -- `denomination_sociale`/`siege_social`.

    Champ manquant -> placeholder textuel explicite, jamais un vide silencieux
    (même convention que `_render_patron_associe_statuts`).
    """
    if officer.associate_id is not None:
        associe = db.query(ProjectAssociate).filter(ProjectAssociate.id == officer.associate_id).first()
        if associe is None:
            return "(associé introuvable -- donnée corrompue)", None
        if associe.type_personne == "personne_morale":
            return associe.denomination_sociale or "(dénomination sociale non renseignée)", associe.siege_social
        return associe.nom_complet or "(nom non renseigné)", associe.adresse

    if officer.type_personne == "personne_morale":
        return officer.denomination_sociale or "(dénomination sociale non renseignée)", officer.siege_social
    return officer.nom_complet or "(nom non renseigné)", officer.adresse


# Libellés des rôles pour les signaux « non désigné » du document (lot B).
_LIBELLES_ROLE = {
    "president": "Président",
    "directeur_general": "Directeur Général",
    "membre_comite": "membre du Comité de Direction",
    "mandataire": "mandataire",
}


def _premier_officier(db: Session, project_id, role: str) -> CompanyOfficer | None:
    """Le mandat de `role` pour ce projet, par ordre de création -- convention
    "premier" (comme les fondateurs, voir `_render_identification_parties_statuts`).

    Limite assumée, pas cachée : pour 'membre_comite' (seul rôle pouvant avoir
    plusieurs lignes, voir docstring du modèle), ne renvoie QUE le premier --
    les clauses actuelles (art. 41) ne demandent qu'"un premier membre",
    jamais la liste complète. À revoir si un futur besoin (lister TOUS les
    membres du comité) apparaît.
    """
    return (
        db.query(CompanyOfficer)
        .filter(CompanyOfficer.project_id == project_id, CompanyOfficer.role == role)
        .order_by(CompanyOfficer.created_at)
        .first()
    )


def _resoudre_variables_officiers_statuts(variables: list[dict], db: Session, project_id) -> dict:
    """Résout les variables identité des dirigeants désignés (Cas A de l'audit
    du 23/09/2026 sur les 9 types `auto_*_associe` non résolus) : art. 39/40/41
    "..._personne_physique" (`auto_nom_complet_associe`/`auto_adresse_associe`)
    et art. 44 + Annexe III clôture (`auto_identite_associe`, mandataire) --
    voir `_ROLE_PAR_NOM_VARIABLE`.

    Lit `company_officers` (table dédiée aux mandats, voir sa docstring) plutôt
    que `project_associates` directement : un dirigeant peut ne pas être
    associé (ex. Président sans capital), donc la source de vérité du RÔLE est
    forcément cette table, jamais une déduction depuis les associés.

    Ne résout RIEN si aucun `CompanyOfficer` de ce rôle n'existe encore pour ce
    projet (l'entrepreneur n'a pas encore désigné son Président/DG/mandataire)
    -- le placeholder reste visible tel quel, même convention que le reste de
    ce fichier (signal visible, jamais un vide silencieux) : la variable n'est
    alors PAS exclue de la saisie manuelle malgré son type `auto_*` (voir
    `_validate_variables`), donc le questionnaire redemande la donnée tant que
    le dirigeant n'est pas désigné.
    """
    pertinentes = [v for v in variables if v["nom"] in _ROLE_PAR_NOM_VARIABLE]
    if not pertinentes:
        return {}

    resolues: dict[str, str] = {}
    officiers_par_role: dict[str, CompanyOfficer | None] = {}
    for var in pertinentes:
        role, champ = _ROLE_PAR_NOM_VARIABLE[var["nom"]]
        if role not in officiers_par_role:
            officiers_par_role[role] = _premier_officier(db, project_id, role)
        officier = officiers_par_role[role]
        if officier is None:
            # Lot B : dirigeant pas encore désigné -> signal visible dans le
            # document (« pour une durée de : , demeurant . » sortait vide).
            resolues[var["nom"]] = f"({_LIBELLES_ROLE[role]} non désigné — page Dirigeants)"
            continue
        if champ == "duree_fonctions":
            # Lu directement sur le mandat, PAS via `_identite_officier` --
            # cette colonne n'a pas d'équivalent sur `project_associates`
            # (voir `_ROLE_PAR_NOM_VARIABLE` ci-dessus), donc aucune logique
            # d'anti-redondance à appliquer ici.
            resolues[var["nom"]] = officier.duree_fonctions or "(durée non renseignée)"
            continue
        identite, adresse = _identite_officier(db, officier)
        if champ in ("nom", "identite"):
            resolues[var["nom"]] = identite
        elif champ == "adresse":
            resolues[var["nom"]] = adresse or "(adresse non renseignée)"
    return resolues


# Champs "personne morale" des dirigeants désignés dans les statuts --
# correction #12 (Président, art. 39), étendue le 24/09/2026 au 1er Directeur
# Général (art. 40) et aux 1ers membres du Comité de Direction (art. 41), qui
# avaient exactement le même trou (8 champs PM en saisie manuelle alors que
# `company_officers` les porte). nom de variable -> (rôle, colonne
# `CompanyOfficer` à lire, ou "representant" pour prénom + nom composés).
_CHAMPS_PM_OFFICIER_PAR_NOM_VARIABLE: dict[str, tuple[str, str]] = {
    f"{prefixe}_{suffixe}": (role, champ)
    for suffixe, role in (
        ("premier_president", "president"),
        ("premier_directeur_general", "directeur_general"),
        ("membre_comite", "membre_comite"),
    )
    for prefixe, champ in (
        ("denomination_sociale", "denomination_sociale"),
        ("forme_juridique", "forme_juridique"),
        ("capital", "capital_social"),
        ("siege_social", "siege_social"),
        ("rcs", "lieu_immatriculation"),
        ("numero_siren", "siren"),
        ("nom_complet_representant", "representant"),
        # Réutilisation de la colonne `adresse` (décision utilisateur du
        # 24/09/2026, pas de colonne dédiée au représentant).
        ("adresse_representant", "adresse"),
    )
}


def _resoudre_variables_officiers_pm_statuts(variables: list[dict], db: Session, project_id) -> dict:
    """Résout les 8 variables des variantes personne morale du Président
    (art. 39), du 1er Directeur Général (art. 40) et des 1ers membres du
    Comité de Direction (art. 41) -- correction #12 de l'audit, étendue le
    24/09/2026 (voir `_CHAMPS_PM_OFFICIER_PAR_NOM_VARIABLE`).

    Erreur initiale de l'audit : "personne morale tierce, aucune table" --
    faux, corrigé après retour utilisateur. `company_officers` porte déjà ces
    champs PM (voir sa docstring : "les 24 variables dirigeants... se
    rempliront depuis cette table").

    Anti-redondance : si ce Président PM est LUI-MÊME un associé personne
    morale du projet (`associate_id` renseigné), ses champs vivent sur
    `project_associates` (mêmes noms de colonnes, voir `project_associate.py`)
    -- jamais dupliqués sur `company_officers`. Sinon, lus directement sur
    `company_officers`.

    `nom_complet_representant_premier_president` (représentant permanent) est
    un champ propre au MANDAT de Président, pas à l'identité de la personne
    morale associée -- il n'existe donc que sur `company_officers` et reste
    en saisie manuelle si ce Président PM est un associé (aucune donnée à
    lire côté `project_associates` pour ce champ précis).

    Même convention que `_resoudre_variables_officiers_statuts` : mandat de
    Président pas encore désigné, ou champ non renseigné -> rien résolu (ou
    placeholder explicite), jamais un vide silencieux ; la variable reste
    alors en saisie manuelle (voir `_validate_variables`).
    """
    pertinentes = [v for v in variables if v["nom"] in _CHAMPS_PM_OFFICIER_PAR_NOM_VARIABLE]
    if not pertinentes:
        return {}

    resolues: dict[str, str] = {}
    sources_par_role: dict[str, tuple | None] = {}
    for var in pertinentes:
        role, champ = _CHAMPS_PM_OFFICIER_PAR_NOM_VARIABLE[var["nom"]]
        if role not in sources_par_role:
            officier = _premier_officier(db, project_id, role)
            associe = None
            if officier is not None and officier.associate_id is not None:
                associe = db.query(ProjectAssociate).filter(ProjectAssociate.id == officier.associate_id).first()
                if associe is None or associe.type_personne != "personne_morale":
                    # Incohérence de données (mandat PM mais associé
                    # introuvable/PP) -- rien résolu pour ce rôle plutôt
                    # qu'une valeur fausse.
                    officier = None
            sources_par_role[role] = (officier, associe) if officier is not None else None
        sources = sources_par_role[role]
        if sources is None:
            # Lot B : même signal visible que pour une personne physique.
            resolues[var["nom"]] = f"({_LIBELLES_ROLE[role]} non désigné — page Dirigeants)"
            continue
        officier, associe = sources
        if champ == "representant":
            prenom, nom = officier.representant_prenom, officier.representant_nom
            valeur = f"{prenom or ''} {nom or ''}".strip()
            resolues[var["nom"]] = valeur or "(représentant non renseigné)"
            continue
        source = associe if associe is not None else officier
        valeur = getattr(source, champ, None)
        if valeur in (None, ""):
            resolues[var["nom"]] = "(non renseigné)"
        else:
            # Capital d'un dirigeant personne morale : format français.
            resolues[var["nom"]] = formater_montant(valeur) if isinstance(valeur, Decimal) else str(valeur)
    return resolues


def _resoudre_signatures_associes(variables: list[dict], db: Session, project_id) -> dict:
    """Lot A (24/09/2026) — `auto_signatures_associes` (clôture) : un bloc de
    signature par associé, plus le Président / Directeur Général s'ils ne
    sont pas associés (ils signent aussi, avec la mention « Bon pour
    acceptation des fonctions »). Jamais saisi : la liste vient
    d'« Équipe & capital » et de la page Dirigeants.

    Personne morale : « Dénomination, représentée par Prénom Nom ». Aucun
    associé -> placeholder visible, jamais un vide."""
    pertinentes = [v for v in variables if v["type"] == "auto_signatures_associes"]
    if not pertinentes:
        return {}

    signataires: list[str] = []
    for a in (
        db.query(ProjectAssociate).filter(ProjectAssociate.project_id == project_id).order_by(ProjectAssociate.created_at)
    ):
        if a.type_personne == "personne_morale":
            representant = f"{a.representant_prenom or ''} {a.representant_nom or ''}".strip()
            nom = a.denomination_sociale or a.nom_complet
            signataires.append(f"{nom}, représentée par {representant or '(représentant non renseigné)'}")
        else:
            signataires.append(a.nom_complet)
    for role, qualite in (("president", "Président"), ("directeur_general", "Directeur Général")):
        officier = _premier_officier(db, project_id, role)
        if officier is not None and officier.associate_id is None:
            identite, _ = _identite_officier(db, officier)
            signataires.append(f"{identite}, en qualité de {qualite}")

    if signataires:
        texte = "\n\n".join(f"{nom}\nSignature : ______________________" for nom in signataires)
    else:
        texte = "(aucun associé renseigné -- signatures à compléter)"
    return {v["nom"]: texte for v in pertinentes}


def _resoudre_variables_apports_statuts(variables: list[dict], db: Session, project_id) -> dict:
    """Résout `auto_montant_apports_numeraire`/`auto_montant_apports_nature`
    (service 1.1.4, Article 6 "recapitulation_apports") -- les 2 SEULS des 9
    nouveaux types `auto_*_associe` du clausier statuts qui sont résolubles
    sans ambiguïté (voir l'audit du 23/09/2026 : les 7 autres, ex.
    `auto_identite_associe`, demandent "l'identité de l'associé qui..." sans
    qu'on puisse garantir qu'un seul associé corresponde -- laissés en saisie
    manuelle, volontairement, plutôt que deviner).

    `project_associates` ne porte pas de montant d'apport par ligne, seulement
    un `pourcentage_capital` et un `type_apport` ('numeraire'/'nature'/
    'industrie') -- le montant se déduit du capital social du projet
    (`ProjectLegalProfile.capital_social`), au prorata du pourcentage cumulé
    des associés du type concerné. Toujours calculable (0 si aucun associé de
    ce type, ou capital social pas encore renseigné) -- exclue de la saisie
    manuelle dans `_validate_variables`.
    """
    types_demandes = {v["type"] for v in variables} & {
        "auto_montant_apports_numeraire",
        "auto_montant_apports_nature",
    }
    if not types_demandes:
        return {}

    legal_profile = db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project_id).first()
    capital_social = legal_profile.capital_social if legal_profile else None
    associes = db.query(ProjectAssociate).filter(ProjectAssociate.project_id == project_id).all()

    resolues: dict[str, str] = {}
    for var in variables:
        if var["type"] == "auto_montant_apports_numeraire":
            type_apport = "numeraire"
        elif var["type"] == "auto_montant_apports_nature":
            type_apport = "nature"
        else:
            continue
        pourcentage = sum(a.pourcentage_capital for a in associes if a.type_apport == type_apport)
        montant = (capital_social * pourcentage / 100) if capital_social is not None else None
        resolues[var["nom"]] = str(montant) if montant is not None else "0"
    return resolues


_SELECTION_RE = re.compile(r"^(\w+)\s*==\s*(?:'([^']*)'|(true|false))$")


def _parser_selection(expression: str) -> tuple[str, object] | None:
    """Parse une expression `selection` du clausier statuts (ex.
    `"type_apport == 'numeraire'"`, `"est_fondateur == true"`) en
    `(champ, valeur)` -- micro-syntaxe volontairement minimale (un seul
    opérateur `==`), PAS un évaluateur générique (`eval`) : les quelques
    expressions du clausier ne justifient pas un langage d'expression
    complet, et `eval` sur une chaîne -- même issue d'un fichier de décisions
    de confiance -- est un anti-pattern qu'aucun besoin réel ici ne justifie.

    `None` si l'expression ne correspond pas à ce format -- une variable
    reste alors sans candidat plutôt que de faire planter le questionnaire
    pour une faute de frappe dans le clausier (signalée à l'audit du
    clausier, pas ici).
    """
    m = _SELECTION_RE.match(expression.strip())
    if not m:
        return None
    champ, valeur_texte, valeur_bool = m.groups()
    if valeur_bool is not None:
        return champ, valeur_bool == "true"
    return champ, valeur_texte


def _candidats_selection_associe(db: Session, project_id, expression: str) -> list[ProjectAssociate]:
    """Associés du projet dont le champ visé par `expression` correspond --
    ex. `"type_apport == 'numeraire'"` -> tous les apporteurs en numéraire,
    `"est_fondateur == true"` -> tous les fondateurs (Article 8
    `fondateur_avantage`)."""
    parsed = _parser_selection(expression)
    if parsed is None:
        return []
    champ, valeur = parsed
    associes = db.query(ProjectAssociate).filter(ProjectAssociate.project_id == project_id).all()
    return [a for a in associes if getattr(a, champ, None) == valeur]


def _identite_associe(a: ProjectAssociate) -> str:
    """Identité affichable d'un associé (personne physique ou morale) --
    utilisée pour les variables `auto_identite_associe` résolues par
    sélection (voir `_resoudre_variables_selection_associe`), volontairement
    plus courte que `_render_patron_associe_statuts` (l'en-tête) : ici la
    variable s'insère AU MILIEU d'une phrase existante du clausier
    ("(identité) apporte à la Société..."), pas un patron d'identification
    complet."""
    if a.type_personne == "personne_morale":
        return a.denomination_sociale or "(dénomination sociale non renseignée)"
    return a.nom_complet or "(nom non renseigné)"


def _selections_requises(db: Session, variables: list[dict], project_id, code_clause: str | None = None) -> dict:
    """Pour le frontend (voir `_clause_payload`), la liste `{id, libelle}`
    des associés concernés par chaque variable dont le champ est résolu PAR
    ASSOCIÉ plutôt que par une saisie unique -- 2 cas distincts, tous deux
    exposés ici pour que le frontend n'ait qu'UNE seule structure à lire :

    - `auto_identite_associe` (Cas C, ex. Article 8 `fondateur_avantage`) :
      un VRAI choix -- le frontend affiche un menu déroulant. Exposée
      seulement si le filtre `selection` retient PLUSIEURS candidats (1 seul
      -> résolution automatique, jamais un choix -- voir
      `_resoudre_variables_selection_associe`). Jamais exposée pour une
      variable de `_VARIABLES_MANDATAIRE` (résolue depuis `company_officers`)
      ni pour `identite_apporteur_nature` dans une clause de
      `_CLAUSES_REPETEES_PAR_ASSOCIE` (répétée pour TOUS, jamais un choix).
    - `texte_par_associe`/`nombre_par_associe` (Cas B, ex. Article 6
      `designation_bien_apporte`, ex. Article 6.2 bis `nombre_actions` d'un
      apport en industrie) : pas un choix -- le frontend affiche UN champ
      (texte ou nombre selon le type) PAR associé listé (même candidat unique
      ou multiple, la saisie reste par associé). Les 2 types partagent
      exactement la même structure d'exposition ici ; seul le type de champ
      affiché par le frontend diffère (texte libre vs. saisie numérique).
    """
    resultat: dict[str, list[dict]] = {}
    for v in variables:
        if v["type"] == "auto_identite_associe":
            if (
                not v.get("selection")
                or v["nom"] in _VARIABLES_MANDATAIRE
                or (code_clause in _CLAUSES_REPETEES_PAR_ASSOCIE)
            ):
                continue
            candidats = _candidats_selection_associe(db, project_id, v["selection"])
            if len(candidats) > 1:
                resultat[v["nom"]] = [{"id": str(a.id), "libelle": _identite_associe(a)} for a in candidats]
        elif v["type"] in ("texte_par_associe", "nombre_par_associe"):
            if not v.get("selection"):
                continue
            candidats = _candidats_selection_associe(db, project_id, v["selection"])
            if candidats:
                resultat[v["nom"]] = [{"id": str(a.id), "libelle": _identite_associe(a)} for a in candidats]
    return resultat


def _resoudre_variables_selection_associe(
    db: Session, variables: list[dict], project_id, valeurs_saisies: dict
) -> dict:
    """Résout les variables `auto_identite_associe` restantes (Cas B Article 6
    "apports", Cas C Article 8 `fondateur_avantage` -- audit du 23/09/2026)
    via leur filtre `selection` :
    - UN SEUL candidat -> résolu automatiquement, jamais demandé (voir
      `_validate_variables`) -- couvre le cas le plus courant (ex. un seul
      apporteur en nature).
    - PLUSIEURS candidats -> `valeurs_saisies[nom]` doit être l'identifiant
      d'un des candidats (imposé par `_validate_variables`), résolu ici en
      son identité affichable.
    - AUCUN candidat -> rien résolu, le placeholder reste visible (même
      convention que le reste de ce fichier).

    Ne couvre PAS la répétition complète de l'art. 6.1 (un paragraphe par
    apporteur numéraire, avec sa propre somme/nombre d'actions) -- seule
    l'IDENTITÉ de l'apporteur est résolue ici ; dette technique assumée,
    signalée à l'utilisateur (23/09/2026) : une vraie répétition de section
    demanderait de faire boucler le questionnaire par associé, changement de
    modèle de données hors du périmètre de cette résolution.
    """
    resolues: dict[str, str] = {}
    for v in variables:
        if v["type"] != "auto_identite_associe" or not v.get("selection") or v["nom"] in _VARIABLES_MANDATAIRE:
            continue
        candidats = _candidats_selection_associe(db, project_id, v["selection"])
        if len(candidats) == 1:
            resolues[v["nom"]] = _identite_associe(candidats[0])
        elif len(candidats) > 1:
            choisi = valeurs_saisies.get(v["nom"])
            associe = next((a for a in candidats if str(a.id) == choisi), None)
            if associe is not None:
                resolues[v["nom"]] = _identite_associe(associe)
    return resolues


def _valeurs_apports_numeraire_par_associe(
    db: Session, session: DocumentGenerationSession
) -> tuple[ContractClauseLibrary, list[tuple[ProjectAssociate, dict]]] | None:
    """Calcule, pour la section 6.1 "Apports en numéraire", le jeu de valeurs
    COMPLET (identité + économiques) de CHAQUE associé `type_apport='numeraire'`
    -- factorisé pour être utilisé à la fois par `_render_apports_numeraire_statuts`
    (assemblage PDF) et `_collect_variable_values` (traçabilité), qui ont
    besoin exactement du même calcul sous 2 formes différentes.

    Limite résolue (23/09/2026, suite à l'audit du Cas B, voir la note du
    clausier, article "apports" : "bloc répété pour chaque associé") :
    `somme`/`nombre_actions` par apporteur ne sont PAS redemandés à
    l'entrepreneur -- même formule déterministe que
    `_resoudre_variables_apports_statuts` (`capital_social * pourcentage_capital
    / 100`, actions au prorata de `ProjectLegalProfile.nombre_actions`) --
    puisqu'ils se déduisent déjà de données existantes. SEULE la politique de
    libération (entièrement/partiellement libérées + fraction si partielle)
    reste une réponse UNIQUE, saisie une fois pour toute la section
    (`session.reponses["apports_numeraire_liberation"]`) et réutilisée
    IDENTIQUE pour chaque apporteur -- une société applique une seule
    politique de libération à sa constitution, pas une par associé.

    Note (25/09/2026, audit complet du clausier) : le paragraphe ci-dessus
    signalait autrefois une limite à 2 apporteurs en NATURE ("1°"/"2°"
    hardcodés) -- CORRIGÉE depuis (voir `_valeurs_apports_nature_par_associe`,
    clause dédiée `apport_nature_identite`, répétition sans limite de nombre).
    Laissé un temps ici par erreur de mise à jour croisée -- retiré, pour ne
    pas laisser une dette déjà résolue induire en erreur un futur lecteur.
    La seule limite du même ORDRE encore réelle porte sur `apports_industrie`
    (art. 6.2 bis) : `identite_apporteur_industrie` passe par le mécanisme
    GÉNÉRIQUE de sélection (`_resoudre_variables_selection_associe`), qui ne
    répète PAS la clause par apporteur -- correct avec 0 ou 1 apporteur en
    industrie (cas normal), mais forcerait un choix unique si 2+ (chaque
    apporteur a pourtant ses propres `prestations_industrie`/`nombre_actions`/
    `pourcentage_benefices`/`pourcentage_pertes`, non déductibles d'une
    formule contrairement à numéraire/nature -- négociés au cas par cas).
    Signalé à l'utilisateur le 25/09/2026, pas corrigé silencieusement : cas
    plus rare (peu de SAS ont plusieurs apporteurs en industrie) et demanderait
    un nouveau mécanisme de saisie "par associé" pour des champs NUMÉRIQUES
    (`texte_par_associe` ne couvre que le texte libre aujourd'hui).

    Retourne `None` si la section n'a pas encore de réponse, a été refusée,
    ou si aucun associé n'a `type_apport='numeraire'` -- rien à produire, cas
    normal (ex. capital 100% en nature), pas une erreur.
    """
    reponse = session.reponses.get("apports_numeraire_liberation")
    if not reponse or not reponse.get("inclus") or not reponse.get("code_clause"):
        return None

    clause = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == session.document_type,
            ContractClauseLibrary.code_clause == reponse["code_clause"],
        )
        .first()
    )
    if clause is None:
        return None

    apporteurs = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == session.project_id, ProjectAssociate.type_apport == "numeraire")
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not apporteurs:
        return None

    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )
    capital_social = legal_profile.capital_social if legal_profile else None
    nombre_actions_total = legal_profile.nombre_actions if legal_profile else None
    valeur_nominale = legal_profile.valeur_nominale if legal_profile else None

    valeurs_partagees = dict(reponse.get("valeurs", {}))
    resultat: list[tuple[ProjectAssociate, dict]] = []
    for a in apporteurs:
        somme = (capital_social * a.pourcentage_capital / 100) if capital_social is not None else None
        actions = (
            round(nombre_actions_total * float(a.pourcentage_capital) / 100)
            if nombre_actions_total is not None
            else None
        )
        valeurs_associe = dict(valeurs_partagees)
        valeurs_associe["identite_apporteur_numeraire"] = _identite_associe(a)
        montant_texte = formater_montant(somme) if somme is not None else "(somme non renseignée)"
        valeurs_associe["somme"] = montant_texte
        valeurs_associe["somme_total"] = montant_texte
        if somme is not None and "fraction_libérée" in valeurs_partagees:
            try:
                fraction = Decimal(str(valeurs_partagees["fraction_libérée"]))
                valeurs_associe["somme_libérée"] = formater_montant(somme * fraction / 100)
            except (TypeError, ValueError, InvalidOperation):
                # fraction non numérique -- laisse le placeholder visible plutôt
                # que de planter le calcul de tous les autres apporteurs.
                pass
        valeurs_associe["nombre_actions"] = str(actions) if actions is not None else "(nombre d'actions non renseigné)"
        valeurs_associe["valeur_nominale"] = (
            formater_montant(valeur_nominale) if valeur_nominale is not None else "(valeur nominale non renseignée)"
        )
        resultat.append((a, valeurs_associe))
    return clause, resultat


def _render_apports_numeraire_statuts(db: Session, session: DocumentGenerationSession) -> list[dict] | None:
    """Rend la section 6.1 "Apports en numéraire" -- UN paragraphe par
    associé `type_apport='numeraire'`, plutôt que le rendu "une réponse = un
    paragraphe" habituel de `_render_clause_texte`. Voir
    `_valeurs_apports_numeraire_par_associe` pour le calcul et les limites
    assumées.
    """
    resultat = _valeurs_apports_numeraire_par_associe(db, session)
    if resultat is None:
        return None
    clause, par_associe = resultat

    runs: list[dict] = []
    for i, (_associe, valeurs_associe) in enumerate(par_associe):
        if i > 0:
            runs.append(_lit("\n\n"))
        runs.extend(statuts_clause_renderer.render_clause_texte(clause.texte_clause, valeurs_associe, clause.variables_requises))
    return runs


def _valeurs_apports_nature_par_associe(
    db: Session, session: DocumentGenerationSession
) -> tuple[ContractClauseLibrary, list[tuple[ProjectAssociate, dict]]] | None:
    """Calcule, pour la clause `apport_nature_identite` (23/09/2026, retouche
    du clausier -- article "apports" séparé en un en-tête statique + cette
    entrée dédiée, voir sa note), le jeu de valeurs de CHAQUE associé
    `type_apport='nature'` -- même principe que
    `_valeurs_apports_numeraire_par_associe`, mais `designation_bien_apporte`
    N'EST PAS déterministe (texte libre décrivant le bien apporté, différent
    par associé) : lu depuis la réponse `texte_par_associe` soumise pour
    cette section (`session.reponses["apport_nature_identite"]["valeurs"]
    ["designation_bien_apporte"]`, un dict `{id_associe: description}` --
    voir `_validate_variables`).
    """
    reponse = session.reponses.get("apport_nature_identite")
    if not reponse or not reponse.get("inclus", True) or not reponse.get("code_clause"):
        return None

    # Correction #4/ex-P2 (audit 23/09/2026) : `description_apport_nature`
    # (colonne persistée sur `project_associates`, migration d3f7a1c9e5b4) a
    # priorité sur la réponse de session -- un associé qui a déjà renseigné
    # cette donnée (ex. dans un précédent document) n'a pas à la ressaisir.
    # La réponse de session sert de repli pour un associé qui n'a pas encore
    # cette colonne remplie. NOTE (dette assumée, pas encore câblée) : rien
    # n'écrit aujourd'hui la réponse de session dans cette colonne -- à faire
    # côté `document_generation_service.py` (point de soumission de la
    # clause), sinon la persistance ne profite qu'aux associés déjà à jour.

    clause = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == session.document_type,
            ContractClauseLibrary.code_clause == reponse["code_clause"],
        )
        .first()
    )
    if clause is None:
        return None

    apporteurs = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == session.project_id, ProjectAssociate.type_apport == "nature")
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not apporteurs:
        return None

    designations = (reponse.get("valeurs") or {}).get("designation_bien_apporte") or {}
    resultat: list[tuple[ProjectAssociate, dict]] = []
    for a in apporteurs:
        valeur = a.description_apport_nature or designations.get(str(a.id)) or "(désignation non renseignée)"
        resultat.append(
            (
                a,
                {
                    "identite_apporteur_nature": _identite_associe(a),
                    "designation_bien_apporte": valeur,
                },
            )
        )
    return clause, resultat


def _render_apports_nature_statuts(db: Session, session: DocumentGenerationSession) -> list[dict] | None:
    """Rend la clause `apport_nature_identite` -- UN paragraphe par associé
    `type_apport='nature'`, remplace l'ancien bricolage à 2 emplacements fixes
    ("1°"/"2°") du clausier d'origine. Voir
    `_valeurs_apports_nature_par_associe` pour le calcul et les limites."""
    resultat = _valeurs_apports_nature_par_associe(db, session)
    if resultat is None:
        return None
    clause, par_associe = resultat

    runs: list[dict] = []
    for i, (_associe, valeurs_associe) in enumerate(par_associe):
        if i > 0:
            runs.append(_lit("\n\n"))
        runs.extend(statuts_clause_renderer.render_clause_texte(clause.texte_clause, valeurs_associe, clause.variables_requises))
    return runs


def _valeurs_dispense_l225_8_1_par_associe(
    db: Session, session: DocumentGenerationSession
) -> tuple[ContractClauseLibrary, list[tuple[ProjectAssociate, dict]]] | None:
    """Calcule, pour la variante `dispense_commissaire_apports_l225_8_1`
    (section `evaluation_apports_nature`, choisie parmi 4 variantes -- voir
    `_selections_requises`/limite du 23/09/2026), le jeu de valeurs de CHAQUE
    apporteur en nature -- ENTIÈREMENT auto-résolu, aucune saisie manuelle :

    - `nature_biens` : réutilise `designation_bien_apporte`, DÉJÀ saisi pour
      ce même associé dans la clause `apport_nature_identite` -- même bien,
      pas de raison de le redemander deux fois.
    - `somme_apport_nature`/`nombre_actions` : même formule déterministe que
      `_valeurs_apports_numeraire_par_associe` (`capital_social *
      pourcentage_capital / 100`, actions au prorata) -- la valeur d'un
      apport en nature est, par construction, celle qui justifie le
      pourcentage de capital reçu en échange.
    - `identite_apporteur_nature`/`valeur_nominale` : identiques aux autres
      clauses nature/numéraire.

    Les 3 AUTRES variantes de cette section (commissaire aux apports
    unanimité/ordonnance, dispense L.227-1) ne référencent AUCUNE de ces
    variables (vérifié le 23/09/2026) -- seule celle-ci avait ce problème.

    Retourne `None` si cette variante n'a pas été choisie, ou si aucun
    associé n'a `type_apport='nature'`.
    """
    reponse = session.reponses.get("evaluation_apports_nature")
    if (
        not reponse
        or not reponse.get("inclus")
        or reponse.get("code_clause") != "dispense_commissaire_apports_l225_8_1"
    ):
        return None

    clause = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == session.document_type,
            ContractClauseLibrary.code_clause == "dispense_commissaire_apports_l225_8_1",
        )
        .first()
    )
    if clause is None:
        return None

    apporteurs = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == session.project_id, ProjectAssociate.type_apport == "nature")
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not apporteurs:
        return None

    legal_profile = (
        db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == session.project_id).first()
    )
    capital_social = legal_profile.capital_social if legal_profile else None
    nombre_actions_total = legal_profile.nombre_actions if legal_profile else None
    valeur_nominale = legal_profile.valeur_nominale if legal_profile else None

    reponse_identite = session.reponses.get("apport_nature_identite") or {}
    designations = (reponse_identite.get("valeurs") or {}).get("designation_bien_apporte") or {}

    resultat: list[tuple[ProjectAssociate, dict]] = []
    for a in apporteurs:
        somme = (capital_social * a.pourcentage_capital / 100) if capital_social is not None else None
        actions = (
            round(nombre_actions_total * float(a.pourcentage_capital) / 100)
            if nombre_actions_total is not None
            else None
        )
        # Correction #4/ex-P2 : même priorité colonne persistée > réponse de
        # session que dans `_valeurs_apports_nature_par_associe`.
        nature_biens = a.description_apport_nature or designations.get(str(a.id)) or "(désignation non renseignée)"
        resultat.append(
            (
                a,
                {
                    "nature_biens": nature_biens,
                    "somme_apport_nature": formater_montant(somme) if somme is not None else "(somme non renseignée)",
                    "identite_apporteur_nature": _identite_associe(a),
                    "nombre_actions": str(actions) if actions is not None else "(nombre d'actions non renseigné)",
                    "valeur_nominale": (
                        formater_montant(valeur_nominale) if valeur_nominale is not None else "(valeur nominale non renseignée)"
                    ),
                },
            )
        )
    return clause, resultat


def _render_dispense_l225_8_1_statuts(db: Session, session: DocumentGenerationSession) -> list[dict] | None:
    """Rend la variante `dispense_commissaire_apports_l225_8_1` -- UN
    paragraphe par apporteur en nature, entièrement auto-résolu. Voir
    `_valeurs_dispense_l225_8_1_par_associe`."""
    resultat = _valeurs_dispense_l225_8_1_par_associe(db, session)
    if resultat is None:
        return None
    clause, par_associe = resultat

    runs: list[dict] = []
    for i, (_associe, valeurs_associe) in enumerate(par_associe):
        if i > 0:
            runs.append(_lit("\n\n"))
        runs.extend(statuts_clause_renderer.render_clause_texte(clause.texte_clause, valeurs_associe, clause.variables_requises))
    return runs


def _valeurs_apports_industrie_par_associe(
    db: Session, session: DocumentGenerationSession
) -> tuple[ContractClauseLibrary, list[tuple[ProjectAssociate, dict]]] | None:
    """Calcule, pour la clause `apports_industrie` (art. 6.2 bis, trou trouvé
    à l'audit complet du clausier du 25/09/2026), le jeu de valeurs de CHAQUE
    associé `type_apport='industrie'` -- même principe que
    `_valeurs_apports_nature_par_associe` (identité répétée automatiquement,
    voir `_CLAUSES_REPETEES_PAR_ASSOCIE`), mais 4 champs par-associé au lieu
    d'1 seul : contrairement à `designation_bien_apporte` (texte),
    `nombre_actions`/`pourcentage_benefices`/`pourcentage_pertes` sont des
    NOMBRES (`nombre_par_associe`, nouveau type -- voir la docstring de
    `_selections_requises`), aucun des 4 n'étant déductible d'une formule
    (contrairement à `somme`/`nombre_actions` pour numéraire/nature : un
    apport en industrie ne concourt jamais au capital, art. 1843-2 C. civ.,
    donc pas de `pourcentage_capital` dont dériver quoi que ce soit -- chaque
    apporteur négocie ses propres modalités/contrepartie).

    Retourne `None` si la section n'a pas encore de réponse, a été refusée
    (`clause_optionnelle`), ou si aucun associé n'a `type_apport='industrie'`
    -- cas normal et de très loin le plus fréquent (l'apport en industrie est
    rare en pratique), pas une erreur.
    """
    reponse = session.reponses.get("apports_industrie")
    if not reponse or not reponse.get("inclus", True) or not reponse.get("code_clause"):
        return None

    clause = (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == session.document_type,
            ContractClauseLibrary.code_clause == reponse["code_clause"],
        )
        .first()
    )
    if clause is None:
        return None

    apporteurs = (
        db.query(ProjectAssociate)
        .filter(ProjectAssociate.project_id == session.project_id, ProjectAssociate.type_apport == "industrie")
        .order_by(ProjectAssociate.created_at)
        .all()
    )
    if not apporteurs:
        return None

    valeurs_saisies = reponse.get("valeurs") or {}
    prestations = valeurs_saisies.get("prestations_industrie") or {}
    nombres_actions = valeurs_saisies.get("nombre_actions") or {}
    pourcentages_benefices = valeurs_saisies.get("pourcentage_benefices") or {}
    pourcentages_pertes = valeurs_saisies.get("pourcentage_pertes") or {}

    resultat: list[tuple[ProjectAssociate, dict]] = []
    for a in apporteurs:
        cle = str(a.id)
        resultat.append(
            (
                a,
                {
                    "identite_apporteur_industrie": _identite_associe(a),
                    "prestations_industrie": prestations.get(cle) or "(prestations non renseignées)",
                    "nombre_actions": str(nombres_actions.get(cle, "")) or "(nombre non renseigné)",
                    "pourcentage_benefices": str(pourcentages_benefices.get(cle, "")) or "(pourcentage non renseigné)",
                    "pourcentage_pertes": str(pourcentages_pertes.get(cle, "")) or "(pourcentage non renseigné)",
                },
            )
        )
    return clause, resultat


def _render_apports_industrie_statuts(db: Session, session: DocumentGenerationSession) -> list[dict] | None:
    """Rend la clause `apports_industrie` -- UN paragraphe par associé
    `type_apport='industrie'`. Voir `_valeurs_apports_industrie_par_associe`
    pour le calcul et les limites."""
    resultat = _valeurs_apports_industrie_par_associe(db, session)
    if resultat is None:
        return None
    clause, par_associe = resultat

    runs: list[dict] = []
    for i, (_associe, valeurs_associe) in enumerate(par_associe):
        if i > 0:
            runs.append(_lit("\n\n"))
        runs.extend(statuts_clause_renderer.render_clause_texte(clause.texte_clause, valeurs_associe, clause.variables_requises))
    return runs


# ---------------------------------------------------------------------------
# Renvois d'article (audit #13, 24/09/2026)
# ---------------------------------------------------------------------------

def _resoudre_references_articles(variables: list[dict], numeros: dict[str, int] | None = None) -> dict:
    """Résout les renvois d'article des statuts (`reference_croisee` portant
    `resout_depuis_section`, ex. "visé à l'article (reference_article_preemption)").

    Avant ce correctif, AUCUN code ne lisait `resout_depuis_section` :
    `_resoudre_variables_reference_croisee` (moteur générique) suit la
    convention du pacte (`depend_de_section` + `valeurs_par_clause` sur la
    variable), absente des statuts -> les 17 renvois sortaient VIDES dans le
    PDF, sans aucun signal.

    Le numéro vient de `article_cible`, écrit sur la variable par le
    générateur (`generate_statuts_sas_v2._variable_sortie`) : `document_templates`
    n'a pas de colonne `article`, et le générateur est déjà la source de vérité
    de la numérotation -- pas de requête, pas de migration.

    Renvoie le numéro même si la section visée n'a pas été remplie : c'est
    voulu (Art. 27 -> Art. 4, phrase conditionnelle "si l'article 4 le
    prévoit"). La PRÉSENCE de l'article visé est garantie par les conditions
    d'affichage de la clause qui contient le renvoi, pas ici.

    Cas limite : `article_cible` absent (JSON de sortie pas régénéré, ou
    section visée inconnue du générateur) -> signal visible plutôt qu'un vide
    silencieux (convention du projet).
    """
    resolues = {}
    for var in variables:
        if var.get("type") != "reference_croisee" or not var.get("resout_depuis_section"):
            continue
        article = var.get("article_cible")
        if (var.get("si_article_absent") or {}).get("mode") == "liaison":
            # Placeholder de liaison (25/09/2026) : le contenu vient d'une
            # autre section -- jamais un numéro (il s'imprimait seul sur une
            # ligne, ex. « 9 » dans la liste des mentions de l'Art. 16).
            resolues[var["nom"]] = ""
        elif article is None:
            resolues[var["nom"]] = "(référence d'article non résolue)"
        elif numeros is None:
            resolues[var["nom"]] = str(article)
        elif str(article) in numeros:
            # Lot B : numéro LOGIQUE du clausier -> numéro AFFICHÉ (articles
            # renumérotés sans trou, voir statuts_sas_numerotation.py).
            resolues[var["nom"]] = str(numeros[str(article)])
        else:
            resolues[var["nom"]] = "(article non inclus dans les statuts)"
    return resolues


_MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
_JOURS_PAR_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _libelle_jour(jour: int) -> str:
    return "1er" if jour == 1 else str(jour)


def _resoudre_exercice_social(variables: list[dict], valeurs: dict) -> dict:
    """Règles A (24/09/2026) -- Art. 30, exercice hors année civile : la fin
    d'exercice (`auto_fin_exercice`) n'est plus demandée, elle est CALCULÉE
    comme la veille du jour d'ouverture (ouverture 1er juillet -> clôture
    30 juin), jamais incohérente. Met aussi le jour d'ouverture au format
    français (« 1er »). Valeurs invalides -> rien (la règle de validité
    `jour_ouverture_valide` a déjà bloqué la saisie)."""
    resultat: dict = {}
    for var in variables:
        if var.get("type") != "auto_fin_exercice":
            continue
        try:
            jour = int(str(valeurs.get(var["jour_de"])).strip())
            mois = _MOIS.index(valeurs.get(var["mois_de"]))
        except (TypeError, ValueError):
            resultat[var["nom"]] = "(jour de clôture non calculable)"
            continue
        if not 1 <= jour <= _JOURS_PAR_MOIS[mois]:
            resultat[var["nom"]] = "(jour de clôture non calculable)"
            continue
        resultat[var["jour_de"]] = _libelle_jour(jour)
        if jour > 1:
            resultat[var["nom"]] = f"{jour - 1} {_MOIS[mois]}"
        else:
            mois_precedent = (mois - 1) % 12
            resultat[var["nom"]] = f"{_JOURS_PAR_MOIS[mois_precedent]} {_MOIS[mois_precedent]}"
    return resultat


def _formater_montants_saisis(variables: list[dict], valeurs: dict) -> dict:
    """Montants SAISIS (type `montant`, ex. somme déposée) au format français
    dans le document : « 10000 » -> « 10 000 » (24/09/2026)."""
    return {
        var["nom"]: formater_montant(valeurs[var["nom"]])
        for var in variables
        if var.get("type") == "montant" and valeurs.get(var["nom"]) not in (None, "")
    }


def _formater_dates_saisies(variables: list[dict], valeurs: dict) -> dict:
    """Lot B (24/09/2026) : dates SAISIES (type `date`, ex. date de signature,
    date de dépôt des fonds) au format français JJ/MM/AAAA dans le document --
    le formulaire envoie l'ISO « 2026-10-01 ». Une valeur non ISO est laissée
    telle quelle (jamais d'erreur au rendu)."""
    resultat = {}
    for var in variables:
        if var.get("type") != "date":
            continue
        valeur = valeurs.get(var["nom"])
        if isinstance(valeur, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
            annee, mois, jour = valeur.split("-")
            resultat[var["nom"]] = f"{jour}/{mois}/{annee}"
    return resultat


# ---------------------------------------------------------------------------
# Sections déduites -- SECTIONS_DERIVEES (audit #19, 24/09/2026)
# ---------------------------------------------------------------------------
#
# Une section "déduite" n'est jamais demandée à l'utilisateur : sa réponse se
# calcule à partir des réponses déjà données. Référentiel explicite plutôt que
# des `if code_section == ...` empilés dans le moteur générique : 3 cas
# existaient (#9, #17, #22), seuil au-delà duquel les exceptions dispersées
# deviennent illisibles. Un futur cas = une ligne ici + une petite fonction.
#
# Contrat de chaque fonction : `f(reponses) -> None | False | str`
#   - None  : rien à déduire, parcours normal (la section est posée) ;
#   - False : section non applicable (sautée, comme `_applicable` -> False) ;
#   - str   : `code_clause` à appliquer automatiquement, sans question.
#     RÈGLE : uniquement une clause sans variable à saisir (renvois et
#     `auto_*` seulement) -- elle est soumise avec `valeurs={}`.
#
# Évaluée APRÈS `_applicable` : les conditions `depend_de_section` du
# template s'appliquent d'abord, la déduction ne fait que compléter.

# Clé réservée dans `session.reponses` où l'écran de choix des facultatifs
# (étape 6 du plan, PAS ENCORE CONSTRUIT) écrira la liste des `code_section`
# cochés. Ne correspond à aucune section : ignorée par le parcours normal.
CLE_FACULTATIFS_CHOISIS = "__facultatifs_choisis__"

# Facultatifs qui restreignent la cession des actions (audit #22) : si l'un
# d'eux est choisi, l'Art. 14 doit être "cession avec restrictions".
_FACULTATIFS_RESTRICTIFS_CESSION = frozenset({"inalienabilite", "droit_preemption", "agrement"})


def _inclus(reponses: dict, code_section: str) -> bool:
    return bool((reponses.get(code_section) or {}).get("inclus"))


def _facultatifs_choisis(reponses: dict) -> set[str] | None:
    """None tant que l'écran de choix des facultatifs n'a pas été validé
    (aujourd'hui : toujours, il n'est pas encore construit)."""
    choix = reponses.get(CLE_FACULTATIFS_CHOISIS)
    return set(choix) if isinstance(choix, list) else None


def _deriver_transmission_actions(reponses: dict):
    # Audit #22 : une restriction cochée -> "avec restrictions", sans question.
    # Aucune restriction cochée (ou écran pas encore validé) -> question
    # maintenue (point de conception laissé ouvert, voir audit #22).
    choix = _facultatifs_choisis(reponses)
    if choix is not None and choix & _FACULTATIFS_RESTRICTIFS_CESSION:
        return "cession_actions_restrictions"
    return None


def _deriver_agrement_notification_preemption(reponses: dict):
    # Audit #15/#18 : la phrase "notification dans le cadre de la préemption"
    # n'existe que si l'agrément ET la préemption sont inclus (double
    # condition, non exprimable par `depend_de_section`).
    if _inclus(reponses, "agrement") and _inclus(reponses, "droit_preemption"):
        return "agrement_notification_preemption"
    return False


def _deriver_agrement_suite(reponses: dict):
    # Audit #17 : la variante du §3 se déduit de la présence de l'Art. 16
    # (traité avant l'Art. 17 dans l'ordre légal).
    if _inclus(reponses, "droit_preemption"):
        return "agrement_suite_avec_preemption"
    return "agrement_suite_sans_preemption"


def _deriver_comite_direction_voix_preponderante(reponses: dict):
    # Correction #9, migrée ici depuis `_applicable` (24/09/2026) : la clause
    # renvoie à la liste de `limitation_pouvoirs_president` (Art. 22) ; sans
    # elle, rien à référencer -> non applicable. Sinon, question normale.
    if not _inclus(reponses, "limitation_pouvoirs_president"):
        return False
    return None


def _exclure_si_non_choisi(article_cible: str):
    # Clauses qui dépendent d'un article placé APRÈS elles (ex. Art. 16 ->
    # agrément Art. 17) : `depend_de_section` ne peut pas l'exprimer (le moteur
    # ne lit que des sections déjà répondues), le générateur les neutralise.
    # Décision du 24/09/2026 : dès que l'écran de choix des facultatifs existe
    # (clé CLE_FACULTATIFS_CHOISIS), la clause est retirée si l'article visé
    # n'a PAS été coché ; sinon, question posée comme avant. Sans sélection
    # (aujourd'hui), comportement inchangé -> aucun risque de régression.
    def _deriver(reponses: dict):
        choix = _facultatifs_choisis(reponses)
        if choix is not None and article_cible not in choix:
            return False
        return None
    return _deriver


def _deriver_exclusion_sans_preemption(reponses: dict):
    # Exclusion + préemption, SANS agrément (sinon : clause combinée).
    if _inclus(reponses, "exclusion") and _inclus(reponses, "droit_preemption") and not _inclus(reponses, "agrement"):
        return "exclusion_sans_preemption"
    return False


def _deriver_exclusion_sans_agrement(reponses: dict):
    # Exclusion + agrément, SANS préemption (sinon : clause combinée).
    if _inclus(reponses, "exclusion") and _inclus(reponses, "agrement") and not _inclus(reponses, "droit_preemption"):
        return "exclusion_sans_agrement"
    return False


def _deriver_exclusion_preemption_et_agrement(reponses: dict):
    # Exclusion + préemption + agrément : clause combinée. Elle a une vraie
    # saisie (`modalites_prix_rachat_exclusion`) -> question posée (None),
    # jamais incluse d'office.
    if _inclus(reponses, "exclusion") and _inclus(reponses, "droit_preemption") and _inclus(reponses, "agrement"):
        return None
    return False


def _deriver_inalienabilite_fin_periode(reponses: dict):
    # "À l'expiration de l'inaliénabilité, les titres sont transmissibles sous
    # réserve des stipulations ci-après" : n'a de sens que si une préemption
    # OU un agrément suit. Les deux articles sont APRÈS l'Art. 15 -> lus dans
    # la sélection des facultatifs. Texte sans variable -> inclus d'office.
    # Sans sélection (session antérieure à l'écran) : question posée comme avant.
    choix = _facultatifs_choisis(reponses)
    if choix is None:
        return None
    if choix & {"droit_preemption", "agrement"}:
        return "inalienabilite_fin_periode"
    return False


def _inclure_si_applicable(code_clause: str):
    # Audit #18 : lignes de l'Art. 27 sans variable, dont la présence se
    # déduit entièrement de l'article lié (condition portée par
    # `depend_de_section`, évaluée avant). Applicable -> incluse sans question.
    return lambda reponses: code_clause


def _deriver_annexe_mandat(reponses: dict):
    """Lot A (24/09/2026) : l'Annexe III (mandat pour les actes entre la
    signature et l'immatriculation) n'existe QUE si l'Art. 44 est inclus --
    c'est elle qui donne ce mandat. Lue sur la RÉPONSE de l'Art. 44 (répondu
    avant la clôture), pas sur l'écran des facultatifs : couvre aussi un
    retrait après coup (« Ne plus inclure cet article »)."""
    reponse = reponses.get("mandat_actes_societe_en_formation") or {}
    return "cloture_annexe_mandat" if reponse.get("inclus") else False


SECTIONS_DERIVEES = {
    "transmission_actions": _deriver_transmission_actions,
    # Décision du 24/09/2026 : les définitions de "transfert"/"titres" sont
    # utilisées par les Art. 15-17 ; elles sont incluses d'office dès que
    # l'Art. 14 = restrictions (condition portée par `depend_de_section`),
    # plus jamais refusables -- texte sans variable, sans risque.
    "definitions_transfert_titre": _inclure_si_applicable("definitions_transfert_titre"),
    # Dépendances vers un article postérieur (effet de bord de l'audit #18).
    "inalienabilite_exception_exclusion_controle": _exclure_si_non_choisi("exclusion"),
    "demande_agrement_tiers": _exclure_si_non_choisi("agrement"),
    "preemption_procedure_agrement": _exclure_si_non_choisi("agrement"),
    "preemption_realisation_transfert": _exclure_si_non_choisi("agrement"),
    "agrement_notification_preemption": _deriver_agrement_notification_preemption,
    "agrement_suite": _deriver_agrement_suite,
    "comite_direction_voix_preponderante": _deriver_comite_direction_voix_preponderante,
    # Art. 20 : 3 ALTERNATIVES du modèle (cession de l'exclu dispensée de
    # préemption seule / d'agrément seul / des deux) -- corrigé le 24/09/2026 :
    # les règles précédentes pouvaient inclure les 3 à la fois.
    "exclusion_sans_preemption": _deriver_exclusion_sans_preemption,
    "exclusion_sans_agrement": _deriver_exclusion_sans_agrement,
    "exclusion_preemption_et_agrement": _deriver_exclusion_preemption_et_agrement,
    # Art. 15 : marqueur double "préemption OU agrément" (dette de l'audit #18).
    "inalienabilite_fin_periode": _deriver_inalienabilite_fin_periode,
    "domaine_reserve_agrement": _inclure_si_applicable("domaine_reserve_agrement"),
    "domaine_reserve_exclusion": _inclure_si_applicable("domaine_reserve_exclusion"),
    "domaine_reserve_comite_direction": _inclure_si_applicable("domaine_reserve_comite_direction"),
    "cloture_annexe_mandat": _deriver_annexe_mandat,
}


def reponse_derivee(code_section: str, reponses: dict) -> dict | None:
    """Réponse à enregistrer automatiquement pour une section déduite, ou
    None si la section doit être posée normalement. La clé `derivee: True`
    permet au bouton "Précédent" de ne jamais revenir sur une section que
    l'utilisateur n'a pas remplie lui-même."""
    fonction = SECTIONS_DERIVEES.get(code_section)
    if fonction is None:
        return None
    return _formater_reponse_derivee(fonction(reponses or {}))


def _formater_reponse_derivee(resultat) -> dict | None:
    """Même contrat que SECTIONS_DERIVEES : None = question posée, False =
    non applicable, code_clause = incluse sans question."""
    if resultat is None:
        return None
    if resultat is False:
        return {"applicable": False, "derivee": True}
    return {"inclus": True, "code_clause": resultat, "variante": resultat, "valeurs": {}, "derivee": True}


# Lot 4 (24/09/2026) — sections de l'Art. 6 qui dépendent des types d'apport
# RÉELS des associés (`project_associates.type_apport`), pas d'une réponse :
# séparé de SECTIONS_DERIVEES (qui ne lit que les réponses) car la source est
# la base. code_section -> (type d'apport requis, code_clause à inclure
# d'office s'il est présent, ou None pour laisser la question).
#   - apport en nature : la désignation du bien vient de "Équipe & capital"
#     (lot 2) -> la clause est incluse sans question ; l'évaluation reste un
#     vrai choix (commissaire aux apports ou dispense).
#   - apport en industrie : question conservée, les prestations et
#     contreparties se saisissent par apporteur (non déductibles).
_SECTIONS_SELON_TYPE_APPORT: dict[str, tuple[str, str | None]] = {
    # En-tête « Apports en numéraire » (lot A) : incluse d'office s'il y a un
    # apporteur en numéraire, retirée sinon (plus de sous-titre orphelin).
    "apports": ("numeraire", "apports"),
    "apports_numeraire_liberation": ("numeraire", None),
    "apport_nature_identite": ("nature", "apport_nature_identite"),
    "evaluation_apports_nature": ("nature", None),
    "apports_industrie": ("industrie", None),
}


# Lot 5 (24/09/2026) — Art. 39-41 : la variante « personne physique /
# personne morale » de la nomination se DÉDUIT du dirigeant désigné dans
# « Informations légales » (`company_officers.type_personne`), jamais posée.
# code_section -> (rôle, variante si personne physique, variante si morale).
_NOMINATIONS_PAR_ROLE: dict[str, tuple[str, str, str]] = {
    "nomination_premier_president": (
        "president", "premier_president_personne_physique", "premier_president_personne_morale",
    ),
    "nomination_premier_directeur_general": (
        "directeur_general", "premier_directeur_general_personne_physique", "premier_directeur_general_personne_morale",
    ),
    "nomination_premiers_membres_comite": (
        "membre_comite", "membre_comite_personne_physique", "membre_comite_personne_morale",
    ),
}


def types_dirigeants(db: Session, project_id) -> dict[str, str]:
    """{rôle: type_personne} du PREMIER dirigeant de chaque rôle -- même
    convention "premier" que `_premier_officier` (c'est lui que lisent les
    clauses)."""
    resultat: dict[str, str] = {}
    for officier in (
        db.query(CompanyOfficer).filter(CompanyOfficer.project_id == project_id).order_by(CompanyOfficer.created_at)
    ):
        resultat.setdefault(officier.role, officier.type_personne)
    return resultat


def reponse_selon_dirigeants(code_section: str, types_par_role: dict[str, str]) -> dict | None:
    """Variante de nomination déduite du dirigeant désigné, ou None (question
    posée) si aucun dirigeant de ce rôle n'est encore désigné -- la future
    validation globale bloquera ce cas (décision utilisateur 24/09/2026)."""
    regle = _NOMINATIONS_PAR_ROLE.get(code_section)
    if regle is None:
        return None
    role, variante_pp, variante_pm = regle
    type_personne = types_par_role.get(role)
    if type_personne is None:
        return None
    return _formater_reponse_derivee(variante_pm if type_personne == "personne_morale" else variante_pp)


def reponse_selon_types_apport(code_section: str, types_apport: set[str]) -> dict | None:
    """Réponse automatique d'une section d'apport selon les types d'apport
    présents dans le projet, ou None si la section n'est pas concernée /
    doit être posée. Aucun apporteur du type -> non applicable (ex. pas
    d'« Évaluation des apports en nature » sans apport en nature). Les
    sections dépendantes (dépôt des fonds) suivent via `depend_de_section`."""
    regle = _SECTIONS_SELON_TYPE_APPORT.get(code_section)
    if regle is None:
        return None
    type_requis, clause_d_office = regle
    if type_requis not in types_apport:
        return _formater_reponse_derivee(False)
    return _formater_reponse_derivee(clause_d_office)


# ---------------------------------------------------------------------------
# Écran de choix des articles facultatifs (audit #19, 24/09/2026)
# ---------------------------------------------------------------------------
#
# Le parcours fait une pause juste avant l'Art. 8 (1er article facultatif ;
# aucun des Art. 1-7 ne dépend d'un facultatif) pour que l'utilisateur coche
# les protections qu'il veut. Son choix est enregistré sous
# CLE_FACULTATIFS_CHOISIS ; ensuite :
#   - toutes les sections d'un article NON coché sont écartées
#     automatiquement (`reponse_facultatif_non_choisi`) ;
#   - les sections d'un article coché sont posées normalement, sans
#     redemander "voulez-vous l'inclure ?" (drapeau renvoyé au frontend) ;
#   - SECTIONS_DERIVEES utilise le choix (Art. 14 déduit, clauses liées).
#
# Pourquoi un référentiel par ARTICLE et pas par section : un article
# facultatif contient plusieurs sections, dont certaines sans condition moteur
# (neutralisées par le générateur) -- raisonner par article garantit qu'aucune
# ne reste proposée quand l'article n'a pas été choisi.
#
# DETTE ASSUMÉE : les `explication` ci-dessous sont des textes courts écrits à
# la main, en attendant les explications générées et relues (étapes 4-5 du
# plan, table `article_explications`) -- à remplacer sans toucher à l'écran.

SECTION_PAUSE_FACULTATIFS = "__choix_facultatifs__"
_SECTION_AVANT_FACULTATIFS = "titre_article_8"

FACULTATIFS_STATUTS: list[dict] = [
    {"code": "avantages_particuliers", "articles": ["8"], "titre": "Avantages particuliers",
     "explication": "Accorder à un associé un avantage spécial (droit de vote supplémentaire, part de bénéfices en plus…) en échange d'un apport ou d'un service particulier. Rare au démarrage : il faut alors faire évaluer l'avantage par un commissaire."},
    {"code": "inalienabilite", "articles": ["15"], "titre": "Inaliénabilité des actions",
     "explication": "Interdire aux associés de vendre leurs actions pendant une durée fixée (10 ans maximum). Utile pour garder l'équipe fondatrice stable au démarrage."},
    {"code": "droit_preemption", "articles": ["16"], "titre": "Droit de préemption",
     "explication": "Si un associé veut vendre ses actions, les autres associés sont prioritaires pour les racheter au même prix. Protège contre l'arrivée d'une personne extérieure."},
    {"code": "agrement", "articles": ["17"], "titre": "Agrément des cessions",
     "explication": "Toute vente d'actions doit être acceptée par les associés, qui peuvent refuser un nouvel associé. Si vous le choisissez, l'article 14 prévoira automatiquement des restrictions de cession, et la clause sera publiée au journal d'annonces légales."},
    {"code": "regime_location_actions", "articles": ["18"], "titre": "Location d'actions",
     "explication": "Dire si les associés peuvent louer leurs actions à quelqu'un. La plupart des startups l'interdisent ou l'encadrent."},
    {"code": "changement_controle", "articles": ["19"], "titre": "Changement de contrôle d'un associé société",
     "explication": "Si un associé est une société et que son propriétaire principal change, les autres associés peuvent réagir (par exemple l'exclure). Utile seulement si une société fait partie des associés."},
    {"code": "exclusion", "articles": ["20"], "titre": "Exclusion d'un associé",
     "explication": "Permettre d'exclure un associé dans des cas prévus à l'avance (faute grave, départ…), en l'obligeant à vendre ses actions à un prix fixé, au besoin par un expert."},
    {"code": "comptes_courants", "articles": ["21"], "titre": "Comptes courants d'associés",
     "explication": "Encadrer l'argent que les associés prêtent à la société (avances en compte courant) : conditions de dépôt et de remboursement."},
    {"code": "directeurs_generaux", "articles": ["23", "40"], "titre": "Directeur(s) Général(aux)",
     "explication": "Prévoir un ou plusieurs Directeurs Généraux à côté du Président, avec les mêmes pouvoirs vis-à-vis des tiers, et nommer le premier dans les statuts."},
    {"code": "comite_direction", "articles": ["24", "41"], "titre": "Comité de Direction",
     "explication": "Créer un Comité de Direction qui prend certaines décisions avec le Président, et nommer ses premiers membres dans les statuts."},
    {"code": "mandat_actes_societe_en_formation", "articles": ["44"], "titre": "Actes avant immatriculation",
     "explication": "Autoriser un associé à signer des actes au nom de la société avant son immatriculation (bail, ouverture de compte…). La société les reprendra automatiquement une fois immatriculée."},
]

_FACULTATIF_PAR_ARTICLE = {article: f for f in FACULTATIFS_STATUTS for article in f["articles"]}
_CODES_FACULTATIFS = frozenset(f["code"] for f in FACULTATIFS_STATUTS)


# Sections qui n'appartiennent à AUCUN article numéroté (code_section ->
# pseudo-article). Leur pseudo-article n'est jamais un facultatif, donc elles
# ne sont jamais écartées par l'écran des facultatifs. Même valeur que la clé
# `article` du JSON généré ("cloture").
SECTIONS_HORS_ARTICLE: dict[str, str] = {
    "cloture_fait_a_signature": "cloture",
    "cloture_annexe_mandat": "cloture",
}


def articles_par_section(sections) -> dict[str, str]:
    """`code_section` -> numéro d'article (str), déduit de l'ordre des sections :
    chaque section appartient au dernier `titre_article_N` qui la précède
    (`document_templates` n'a pas de colonne `article`, voir audit #13).
    `sections` doit être trié par `ordre` (c'est le cas de `_sections`)."""
    courant = None
    resultat = {}
    for s in sections:
        code = s.code_section
        if code.startswith("titre_article_"):
            courant = code[len("titre_article_"):]
        elif code in SECTIONS_HORS_ARTICLE:
            # Lot C (24/09/2026) : la clôture suit le dernier article (44)
            # sans en faire partie. Sans cette coupure, elle était rattachée
            # à l'Art. 44 (facultatif) et disparaissait -- question ET texte
            # -- dès que l'Art. 44 n'était pas coché.
            courant = SECTIONS_HORS_ARTICLE[code]
        resultat[code] = courant
    return resultat


def doit_faire_pause_facultatifs(code_section: str) -> bool:
    """Vrai quand le parcours atteint l'Art. 8. Appelé seulement pour une
    section pas encore traitée : une session déjà avancée au-delà (titre de
    l'Art. 8 déjà marqué) ne fait jamais la pause -> aucune régression."""
    return code_section == _SECTION_AVANT_FACULTATIFS


def reponse_facultatif_non_choisi(article: str | None, reponses: dict) -> dict | None:
    """Réponse "exclu" pour une section d'un article facultatif NON coché,
    None sinon (ou si l'écran n'a pas encore été validé)."""
    choix = _facultatifs_choisis(reponses)
    facultatif = _FACULTATIF_PAR_ARTICLE.get(article or "")
    if choix is None or facultatif is None or facultatif["code"] in choix:
        return None
    return {"inclus": False, "facultatif_non_choisi": True, "derivee": True}


def est_article_facultatif_choisi(article: str | None, reponses: dict) -> bool:
    choix = _facultatifs_choisis(reponses)
    facultatif = _FACULTATIF_PAR_ARTICLE.get(article or "")
    return bool(choix is not None and facultatif is not None and facultatif["code"] in choix)


def code_facultatif_de_l_article(article: str | None) -> str | None:
    facultatif = _FACULTATIF_PAR_ARTICLE.get(article or "")
    return facultatif["code"] if facultatif else None


def liste_facultatifs(reponses: dict, explications_validees: dict[str, str] | None = None) -> list[dict]:
    """Liste affichée par l'écran de choix ; `choisi` pré-rempli avec le
    choix précédent si l'utilisateur revient sur l'écran (bouton Précédent).

    `explications_validees` ({code: texte}, étape 5 de la refonte) : les
    explications générées par LLM ET relues par un humain
    (`article_explications`, statut `valide_humain`). À défaut pour un
    article, le texte provisoire de `FACULTATIFS_STATUTS` est affiché —
    l'écran fonctionne donc avant, pendant et après la relecture."""
    choix = _facultatifs_choisis(reponses) or set()
    explications_validees = explications_validees or {}
    return [
        {"code": f["code"], "titre": f["titre"], "articles": f["articles"],
         "explication": explications_validees.get(f["code"], f["explication"]), "choisi": f["code"] in choix}
        for f in FACULTATIFS_STATUTS
    ]


def valider_choix_facultatifs(codes_choisis: list[str]) -> list[str]:
    """Refuse un code inconnu (entrée API) ; renvoie la liste dédoublonnée,
    dans l'ordre du référentiel."""
    inconnus = set(codes_choisis) - _CODES_FACULTATIFS
    if inconnus:
        raise ValueError(f"Article(s) facultatif(s) inconnu(s) : {', '.join(sorted(inconnus))}.")
    choisis = set(codes_choisis)
    return [f["code"] for f in FACULTATIFS_STATUTS if f["code"] in choisis]
