"""Règles de validité vérifiées PAR CODE sur les champs saisis des statuts
(service 1.1.4, niveau A du garde-fou — 24/09/2026).

Pourquoi : les critères de `clause_validity_criteria` (« fraction libérée
≥ 50 % », « inaliénabilité ≤ 10 ans »…) n'étaient donnés qu'au LLM, qui ne
voit que les champs TEXTE -- les champs chiffrés n'étaient donc jamais
contrôlés (10 % de libération passait). Une limite chiffrée se vérifie par du
code : gratuit, instantané, toujours le même résultat.

Contrat d'un critère vérifiable (`valeur_limite`, JSON du clausier) :
- cible : `variable` (une variable ; si sa valeur est saisie PAR ASSOCIÉ,
  chaque valeur est vérifiée) ou `variables` (plusieurs, pour une somme) ;
- bornes sur une valeur (nombre OU date) : `min`, `max`, `min_exclu`,
  `max_exclu`, `min_variable` / `max_variable` (≥ / ≤ une autre variable de
  la même section) ;
- dates, par rapport à aujourd'hui : `min_jours` / `max_jours` (ex.
  `min_jours: -365` = pas plus d'un an dans le passé ; `min_jours: 1` =
  strictement dans le futur) ;
- plusieurs variables : `min` (chacune) et `somme_max_exclue` ;
- jour + mois : `jour_variable` + `mois_variable` (jour existant dans ce
  mois), `exclure` = liste de [jour, mois] interdits ;
- `gravite` : `bloquant` (défaut) ou `avertissement` (l'utilisateur peut
  confirmer et continuer).
Un critère sans cible n'est pas vérifiable par code (ex. « prix
déterminable ») : ignoré ici, laissé au LLM / à la validation globale.

Règle intégrée en plus des critères : un `nombre`/`montant` saisi (y compris
par associé) ne peut pas être négatif -- sauf si un critère fixe déjà un
minimum pour ce champ (sinon deux messages pour la même erreur).

Chaque problème porte un `message` complet (affiché dans « Détails ») et un
`message_court` (une ligne sous le champ), plus `associe_id` pour une saisie
par associé (le frontend affiche l'erreur sous la case de cet associé).

Fonctions pures (aucun accès base, `aujourdhui` injectable) : testables
directement.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

GRAVITE_BLOQUANT = "bloquant"
GRAVITE_AVERTISSEMENT = "avertissement"

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
# Année non bissextile : un exercice qui s'ouvrirait le 29 février
# n'existerait qu'une année sur quatre.
_JOURS_PAR_MOIS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

_UNITES = {"pourcentage": " %", "annees": " ans", "jours": " jours", "euros": " €", "exemplaires": "", "membres": ""}
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valeur(brute) -> Decimal | date | None:
    """Valeur saisie -> Decimal (nombre) ou date (ISO), None sinon (absente,
    non numérique : le contrôle de type reste celui de `_validate_variables`)."""
    if brute is None or isinstance(brute, (dict, list, bool)):
        return None
    texte = str(brute).strip()
    if _ISO_RE.match(texte):
        try:
            return date.fromisoformat(texte)
        except ValueError:
            return None
    try:
        return Decimal(texte.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def _fmt(v: Decimal | date, unite: str | None = None) -> str:
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    texte = format(v.normalize(), "f") if v == v.to_integral() else str(v)
    suffixe = _UNITES.get(unite or "", "")
    if unite in ("jours", "annees") and abs(v) <= 1:
        suffixe = suffixe[:-1]  # « 1 jour », « 0 an » (singulier)
    return texte + suffixe


def _borne(brute, reference: Decimal | date) -> Decimal | date:
    """Borne du clausier dans le même type que la valeur comparée."""
    if isinstance(reference, date):
        return date.fromisoformat(str(brute))
    return Decimal(str(brute))


def _probleme(
    critere: dict | None, variable: str, libelle: str, message: str, court: str, associe_id: str | None = None
) -> dict:
    limite = (critere or {}).get("valeur_limite") or {}
    return {
        "variable": variable,
        "associe_id": associe_id,
        "libelle": libelle,
        "message": message,
        "message_court": court,
        "base_legale": (critere or {}).get("base_legale"),
        "gravite": limite.get("gravite", GRAVITE_BLOQUANT),
    }


def _valeurs_cibles(
    valeurs: dict, variable: str, libelle: str, noms_associes: dict
) -> list[tuple[str, object, str | None]]:
    """[(libellé affiché, valeur brute, id associé)] : une entrée, ou une par
    associé pour une saisie `*_par_associe` ({id_associé: valeur})."""
    brute = valeurs.get(variable)
    if isinstance(brute, dict):
        return [(f"{libelle} — {noms_associes.get(str(cle), 'associé')}", v, str(cle)) for cle, v in brute.items()]
    return [(libelle, brute, None)]


def _verifier_valeur(critere, variable, libelle, v, valeurs, libelles, aujourdhui, associe_id=None) -> list[dict]:
    limite = critere.get("valeur_limite") or {}
    unite = limite.get("unite")
    problemes = []

    def probleme(message: str, court: str) -> dict:
        return _probleme(critere, variable, libelle, message, court, associe_id)

    for cle, viole, texte, court in (
        ("min", lambda b: v < b, "doit être au moins {b}", "Minimum : {b}"),
        ("min_exclu", lambda b: v <= b, "doit être strictement supérieur à {b}", "Doit dépasser {b}"),
        ("max", lambda b: v > b, "ne peut pas dépasser {b}", "Maximum : {b}"),
        ("max_exclu", lambda b: v >= b, "doit être strictement inférieur à {b}", "Doit rester sous {b}"),
    ):
        if cle in limite:
            try:
                borne = _borne(limite[cle], v)
            except (ValueError, InvalidOperation):
                continue  # borne incompatible avec le type saisi : critère mal écrit, ignoré
            if viole(borne):
                b = _fmt(borne, unite)
                problemes.append(probleme(f"{_fmt(v, unite)} : {texte.format(b=b)}.", court.format(b=b)))

    for cle, viole, texte, court in (
        ("min_variable", lambda a: v < a, "doit être au moins égal à", "Au moins {a}"),
        ("max_variable", lambda a: v > a, "ne peut pas dépasser", "Au plus {a}"),
    ):
        if cle in limite:
            autre = _valeur(valeurs.get(limite[cle]))
            if autre is not None and type(autre) is type(v) and viole(autre):
                nom_autre = libelles.get(limite[cle], limite[cle])
                a = _fmt(autre, unite)
                problemes.append(
                    probleme(f"{_fmt(v, unite)} : {texte} « {nom_autre} » ({a}).", court.format(a=a))
                )

    if isinstance(v, date):
        ecart = (v - aujourdhui).days
        if "min_jours" in limite and ecart < int(limite["min_jours"]):
            n = int(limite["min_jours"])
            attendu, court = (
                ("doit être postérieure à aujourd'hui", "Date future requise") if n == 1 else
                ("ne peut pas être passée", "Date passée") if n == 0 else
                (f"ne doit pas dater de plus de {-n} jours", "Date trop ancienne")
            )
            problemes.append(probleme(f"{_fmt(v)} : {attendu}.", court))
        if "max_jours" in limite and ecart > int(limite["max_jours"]):
            n = int(limite["max_jours"])
            attendu, court = (
                ("ne devrait pas être dans le futur", "Date dans le futur") if n == 0 else
                (f"ne devrait pas dépasser {n} jours à partir d'aujourd'hui", "Date trop lointaine")
            )
            problemes.append(probleme(f"{_fmt(v)} : {attendu}.", court))
    return problemes


def _verifier_jour_mois(critere: dict, valeurs: dict, libelles: dict) -> list[dict]:
    limite = critere["valeur_limite"]
    var_jour, var_mois = limite["jour_variable"], limite["mois_variable"]
    jour, mois = _valeur(valeurs.get(var_jour)), valeurs.get(var_mois)
    if jour is None or not isinstance(jour, Decimal) or mois not in MOIS:
        return []
    libelle = libelles.get(var_jour, var_jour)
    maximum = _JOURS_PAR_MOIS[MOIS.index(mois)]
    if jour != jour.to_integral() or not 1 <= jour <= maximum:
        return [
            _probleme(critere, var_jour, libelle, f"le {_fmt(jour)} {mois} n'existe pas (1 à {maximum}).", "Jour inexistant dans ce mois")
        ]
    for jour_interdit, mois_interdit in limite.get("exclure", []):
        if int(jour) == int(jour_interdit) and mois == mois_interdit:
            return [
                _probleme(critere, var_jour, libelle, critere.get("description_critere") or "date non autorisée.", "Date non autorisée")
            ]
    return []


def critere_verifiable_par_code(critere: dict) -> bool:
    """Vrai si ce module vérifie le critère (il a une cible). Les autres
    (« prix déterminable »…) sont laissés au garde-fou LLM (niveau B), qui
    ne reçoit donc jamais un critère déjà contrôlé ici."""
    limite = critere.get("valeur_limite") or {}
    return bool(limite.get("variable") or limite.get("variables") or limite.get("jour_variable"))


def _verifier_critere(critere, valeurs, libelles, noms_associes, aujourdhui) -> list[dict]:
    limite = critere.get("valeur_limite") or {}
    unite = limite.get("unite")

    if limite.get("jour_variable") and limite.get("mois_variable"):
        return _verifier_jour_mois(critere, valeurs, libelles)

    variables = limite.get("variables")
    if variables:
        nombres = [_valeur(valeurs.get(v)) for v in variables]
        if any(not isinstance(n, Decimal) for n in nombres):
            return []  # section incomplète : le contrôle de type s'en charge
        problemes = []
        if "min" in limite:
            for v, n in zip(variables, nombres):
                if n < Decimal(str(limite["min"])):
                    b = _fmt(Decimal(str(limite["min"])), unite)
                    problemes.append(
                        _probleme(critere, v, libelles.get(v, v), f"{_fmt(n, unite)} : doit être au moins {b}.", f"Minimum : {b}")
                    )
        if "somme_max_exclue" in limite and sum(nombres) >= Decimal(str(limite["somme_max_exclue"])):
            noms = " + ".join(f"« {libelles.get(v, v)} »" for v in variables)
            problemes.append(
                _probleme(
                    critere, variables[0], libelles.get(variables[0], variables[0]),
                    f"{noms} = {_fmt(sum(nombres), unite)} : doit rester inférieur à {_fmt(Decimal(str(limite['somme_max_exclue'])), unite)}.",
                    f"Total trop élevé ({_fmt(sum(nombres), unite)})",
                )
            )
        return problemes

    variable = limite.get("variable")
    if not variable:
        return []  # critère non vérifiable par code
    problemes = []
    for libelle, brute, associe_id in _valeurs_cibles(valeurs, variable, libelles.get(variable, variable), noms_associes):
        v = _valeur(brute)
        if v is not None:
            problemes.extend(_verifier_valeur(critere, variable, libelle, v, valeurs, libelles, aujourdhui, associe_id))
    return problemes


def _variables_avec_minimum(criteres: list[dict]) -> set[str]:
    """Variables dont un critère fixe déjà un minimum : la règle « pas de
    valeur négative » y ferait doublon (« -12 : négatif » + « -12 : au
    moins 1 jour » pour la même saisie)."""
    noms: set[str] = set()
    for critere in criteres:
        limite = critere.get("valeur_limite") or {}
        if "min" in limite or "min_exclu" in limite:
            noms |= {limite.get("variable")} | set(limite.get("variables") or [])
    noms.discard(None)
    return noms


def verifier_regles(
    variables_requises: list[dict],
    criteres: list[dict],
    valeurs: dict,
    *,
    noms_associes: dict[str, str] | None = None,
    aujourdhui: date | None = None,
) -> list[dict]:
    """Tous les problèmes d'une soumission (jamais seulement le premier).

    `variables_requises` : définition des variables de la clause ;
    `criteres` : critères de la clause (`valeur_limite`, `base_legale`,
    `description_critere`) ; `valeurs` : valeurs saisies ; `noms_associes`
    : {id: nom} pour nommer l'associé d'une saisie par associé. Renvoie des
    dicts {variable, associe_id, libelle, message, message_court,
    base_legale, gravite}."""
    noms_associes = noms_associes or {}
    aujourdhui = aujourdhui or date.today()
    libelles = {v["nom"]: v.get("libelle", v["nom"]) for v in variables_requises}
    problemes: list[dict] = []
    avec_minimum = _variables_avec_minimum(criteres)

    for v in variables_requises:
        if v.get("type") not in ("nombre", "montant", "nombre_par_associe") or v["nom"] in avec_minimum:
            continue
        for libelle, brute, associe_id in _valeurs_cibles(valeurs, v["nom"], libelles[v["nom"]], noms_associes):
            n = _valeur(brute)
            if isinstance(n, Decimal) and n < 0:
                problemes.append(
                    _probleme(None, v["nom"], libelle, "ne peut pas être négatif.", "Pas de valeur négative", associe_id)
                )

    for critere in criteres:
        problemes.extend(_verifier_critere(critere, valeurs, libelles, noms_associes, aujourdhui))
    return problemes
