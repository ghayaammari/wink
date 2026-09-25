"""Primitives de rendu PARTAGÉES entre les moteurs de document (pacte de
fondateurs, statuts SAS, tout futur `document_type`) -- extrait de
`document_generation_service.py` le 23/09/2026.

Pourquoi ce fichier existe : le clausier pacte et le clausier statuts SAS
utilisent 2 conventions DIFFÉRENTES pour écrire un placeholder dans
`texte_clause` -- le pacte écrit `(libelle)` (ex. "(nombre)"), les statuts
écrivent `(nom)` (ex. "(capital_social)"), décision documentée dans
`generate_statuts_sas_v2.py::valider_article()`. L'ancienne fonction unique
`_render_clause_texte` (`document_generation_service.py`) ne connaissait que
la convention pacte -- appliquée telle quelle aux statuts, elle ne
substituait presque aucune variable (174/176 variables du clausier statuts
ne matchaient jamais leur placeholder).

Décision actée avec l'utilisateur (23/09/2026) : PAS de paramètre ajouté à
la fonction partagée (trop risqué pour le pacte, un seul point de code
partagé par les 2 documents), mais pas de duplication complète non plus (le
squelette de substitution -- résolution des gabarits `valeurs_par_choix`,
marquage par sentinelles, découpage en runs -- est identique à 100% entre
les 2 documents, seule la CLÉ de recherche du placeholder diffère). D'où un
patron "Template Method" : `ClauseRendererBase.render_clause_texte` porte le
squelette commun, `_placeholder_key` est le seul point de variation,
redéfini par document_type dans `pacte_fondateurs_renderer.py`/
`statuts_sas_renderer.py`. Un futur document_type avec encore une autre
convention n'a qu'à ajouter une 3e sous-classe ici, sans toucher ni au
squelette ni aux 2 renderers existants.
"""
import re


def _lit(texte: str) -> dict:
    return {"texte": texte, "valeur_utilisateur": False, "nom_variable": None}


def _val(texte: str, nom_variable: str) -> dict:
    return {"texte": texte, "valeur_utilisateur": True, "nom_variable": nom_variable}


# ---------------------------------------------------------------------------
# Donnée projet manquante (23/09/2026, service 1.1.13 -- décision actée avec
# l'utilisateur : alerter au début, corriger pendant, bloquer à la fin)
# ---------------------------------------------------------------------------


class ValeurManquante(str):
    """Valeur de remplacement pour une donnée PROJET absente (profil juridique
    ou associé) -- renvoyée par les résolveurs `auto_*` à la place de l'ancien
    placeholder textuel "(... non renseigné)".

    Sous-classe de `str` (pas un nouveau type à gérer partout) : tout le code
    existant qui la traite comme une chaîne (substitution, `str(...)`,
    sérialisation JSON de `valeurs_auto_resolues`) continue de fonctionner à
    l'identique. Seuls les 2 endroits qui ont besoin de la distinguer le font
    par `isinstance` : le rendu en runs (`render_clause_texte`, marque le run
    `manquant=True` -> orange dans le PDF) et la détection des données
    manquantes (`document_generation_service._donnees_manquantes`).

    `sources` : où corriger -- liste de `{table, champ, libelle, format,
    associe_id, associe_nom}` (liste et pas un seul dict : un même run peut
    dépendre de 2 colonnes, ex. représentant = prénom + nom).
    """

    sources: list[dict]

    def __new__(cls, libelle: str, sources: list[dict]):
        obj = super().__new__(cls, f"[{libelle} — à compléter]")
        obj.sources = sources
        return obj


# Libellé affiché à l'entrepreneur + format de saisie attendu (pour que le
# frontend choisisse le bon champ de formulaire) -- par COLONNE source, pas par
# variable de clause : le libellé d'une variable du clausier ("capital",
# "type de société"...) est une clé de placeholder, pas un texte destiné à
# l'utilisateur. Une colonne absente d'ici retombe sur le libellé de la
# variable et le format "texte" (dégradation lisible, pas d'erreur).
_CHAMPS_PROFIL_JURIDIQUE: dict[str, tuple[str, str]] = {
    "legal_name": ("Dénomination sociale", "texte"),
    "legal_form": ("Forme juridique", "texte"),
    "registered_address": ("Adresse du siège social", "adresse"),
    "capital_social": ("Capital social (€)", "montant"),
    "lieu_immatriculation": ("Ville d'immatriculation (RCS)", "texte"),
    "siren": ("Numéro SIREN", "siren"),
    "objet_social": ("Objet social (activités de la société)", "texte_long"),
    "nombre_actions": ("Nombre d'actions", "entier"),
    "valeur_nominale": ("Valeur nominale d'une action (€)", "montant"),
    "duree_societe": ("Durée de la société (années)", "entier"),
}

_CHAMPS_ASSOCIE: dict[str, tuple[str, str]] = {
    "nom_complet": ("Nom complet", "texte"),
    "date_naissance": ("Date de naissance", "date"),
    "adresse": ("Adresse", "texte"),
    "denomination_sociale": ("Dénomination sociale", "texte"),
    "type_societe": ("Forme de la société", "texte"),
    "capital_social": ("Capital social (€)", "montant"),
    "siege_social": ("Siège social", "texte"),
    "lieu_immatriculation": ("Ville d'immatriculation (RCS)", "texte"),
    "numero_siren": ("Numéro SIREN", "siren"),
    "representant_prenom": ("Prénom du représentant", "texte"),
    "representant_nom": ("Nom du représentant", "texte"),
    "representant_qualite": ("Qualité du représentant", "texte"),
}


def source_profil(champ: str, libelle_defaut: str | None = None) -> dict:
    libelle, fmt = _CHAMPS_PROFIL_JURIDIQUE.get(champ, (libelle_defaut or champ, "texte"))
    return {
        "table": "project_legal_profiles",
        "champ": champ,
        "libelle": libelle,
        "format": fmt,
        "associe_id": None,
        "associe_nom": None,
    }


def source_associe(associe, champ: str) -> dict:
    libelle, fmt = _CHAMPS_ASSOCIE.get(champ, (champ, "texte"))
    return {
        "table": "project_associates",
        "champ": champ,
        "libelle": libelle,
        "format": fmt,
        "associe_id": str(associe.id),
        "associe_nom": associe.nom_complet or associe.denomination_sociale,
    }


def manquant_profil(champ: str, libelle_defaut: str | None = None) -> ValeurManquante:
    source = source_profil(champ, libelle_defaut)
    return ValeurManquante(source["libelle"], [source])


def manquant_associe(associe, *champs: str, libelle: str | None = None) -> ValeurManquante:
    sources = [source_associe(associe, c) for c in champs]
    return ValeurManquante(libelle or sources[0]["libelle"], sources)


def _manquant(valeur: ValeurManquante, nom_variable: str) -> dict:
    """Run d'une donnée projet manquante : `valeur_utilisateur=True` (c'est
    bien une valeur injectée, même position dans le texte) + `manquant=True`
    (orange au lieu de rouge dans le PDF) + `sources` (où la corriger)."""
    return {
        "texte": str(valeur),
        "valeur_utilisateur": True,
        "nom_variable": nom_variable,
        "manquant": True,
        "sources": valeur.sources,
    }


def run_valeur(valeur, nom_variable: str) -> dict:
    """`_val` ou `_manquant` selon la nature de `valeur` -- évite un `if`
    répété à chaque champ dans les patrons d'identification des associés."""
    if isinstance(valeur, ValeurManquante):
        return _manquant(valeur, nom_variable)
    return _val(str(valeur), nom_variable)


class ClauseRendererBase:
    """Sous-classer et redéfinir `_placeholder_key` pour un document_type dont
    le clausier utilise encore une autre convention de placeholder que
    `libelle`/`nom`. Ne PAS redéfinir `render_clause_texte` elle-même sauf si
    le MÉCANISME de substitution doit changer (pas seulement la clé cherchée)
    -- dans ce cas, dupliquer entièrement plutôt que de complexifier ce
    squelette pour un besoin encore hypothétique (accord explicite de
    l'utilisateur, 23/09/2026 : pas de généralisation avant qu'un 2e besoin
    réel n'apparaisse)."""

    def _placeholder_key(self, var: dict) -> str:
        raise NotImplementedError

    def render_clause_texte(self, clause_texte: str, valeurs: dict, variables: list[dict]) -> list[dict]:
        """Remplace chaque placeholder brut du texte source par la valeur
        saisie/résolue pour la variable correspondante -- retourne des "runs"
        (liste de segments `{texte, valeur_utilisateur, nom_variable}`)
        plutôt qu'une chaîne assemblée : `render_document_as_pdf` colore en
        rouge tout run `valeur_utilisateur=True` (exigence utilisateur,
        21/09/2026 -- TOUTE valeur injectée, saisie ou auto-résolue).
        Remplacement littéral, pas de moteur de templating : le texte source
        contient les parenthèses telles quelles, on les retire au passage
        plutôt que de les garder dans le document final signé.

        IDENTIQUE ligne pour ligne à l'ancienne fonction libre
        `_render_clause_texte` (document_generation_service.py), sauf que la
        clé de recherche du placeholder (`var['libelle']` ou `var['nom']`)
        vient maintenant de `self._placeholder_key(var)` -- voir la
        docstring de module pour le pourquoi. Aucun changement de
        comportement pour le pacte (qui redéfinit `_placeholder_key` pour
        retourner `libelle`, exactement comme avant).

        Implémentation : chaque placeholder est d'abord remplacé par un
        marqueur sentinelle unique portant le nom de variable + la valeur
        (`\\x00nom\\x00valeur\\x00`), avec les mêmes règles `.replace()` que
        l'ancienne version (donc les mêmes limites assumées : un placeholder
        identique répété dans le texte source donnerait plusieurs runs avec
        le même `nom_variable`, aucun cas réel aujourd'hui). Le texte final
        est ensuite découpé sur ces marqueurs pour produire la liste de
        runs, sans jamais risquer qu'un `\\x00` apparaisse dans une vraie
        valeur saisie (caractère non imprimable, absent de toute saisie
        utilisateur normale).

        `valeurs_par_choix` (dict sur une variable `type='choix'`, ex.
        "(l'intégralité/au moins X %)" à l'article 7.5 du pacte) : certains
        blancs représentent en réalité 2 saisies distinctes -- un choix
        (`regle_distribution` ici) + un nombre qui ne s'applique que pour UNE
        des options (`seuil_pourcentage`, actif seulement si
        `regle_distribution="pourcentage minimum"`, via le mécanisme
        `depend_de_variable`/`depend_de_valeurs`). `valeurs_par_choix`
        associe l'option choisie à un gabarit qui peut référencer
        `{nom_autre_variable}` -- résolu ici plutôt que par un remplacement
        séquentiel, pour ne substituer la variable dépendante
        (`seuil_pourcentage`) qu'À L'INTÉRIEUR du gabarit de l'option qui la
        rend applicable, jamais comme un 2e placeholder autonome dans le
        texte.
        """
        valeurs_resolues = dict(valeurs)
        for var in variables:
            gabarits = var.get("valeurs_par_choix")
            if not gabarits or var["type"] != "choix":
                continue
            choix_fait = valeurs.get(var["nom"])
            gabarit = gabarits.get(choix_fait)
            if gabarit is None:
                continue
            try:
                valeurs_resolues[var["nom"]] = gabarit.format(**valeurs)
            except KeyError:
                # variable référencée par le gabarit pas encore renseignée --
                # signal visible (placeholder du gabarit laissé tel quel), même
                # choix que le reste de cette fonction plutôt qu'un vide silencieux.
                valeurs_resolues[var["nom"]] = gabarit

        marque = clause_texte
        # `ValeurManquante` perd son type au `str(...).strip()` ci-dessous --
        # gardée de côté par nom de variable pour reconstruire un run
        # `manquant=True` (orange) au lieu d'un run `_val` normal (rouge).
        manquantes: dict[str, ValeurManquante] = {}
        for var in variables:
            placeholder = f"({self._placeholder_key(var)})"
            brut = valeurs_resolues.get(var["nom"], "")
            if isinstance(brut, ValeurManquante):
                manquantes[var["nom"]] = brut
            value = str(brut).strip()
            marque = marque.replace(placeholder, f"\x00{var['nom']}\x00{value}\x00")

        segments = re.split(r"\x00([^\x00]+)\x00([^\x00]*)\x00", marque)
        runs: list[dict] = []
        if segments[0]:
            runs.append(_lit(segments[0]))
        i = 1
        while i < len(segments):
            nom = segments[i]
            runs.append(_manquant(manquantes[nom], nom) if nom in manquantes else _val(segments[i + 1], nom))
            texte_suivant = segments[i + 2] if i + 2 < len(segments) else ""
            if texte_suivant:
                runs.append(_lit(texte_suivant))
            i += 3
        return runs
