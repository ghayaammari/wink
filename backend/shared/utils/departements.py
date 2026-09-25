"""Référentiel des départements français (codes officiels INSEE).

Utilitaire pur partagé (même dossier que `formatting.py`) :
- `departement_depuis_code_postal` : page Annonce légale (1.1.5), pour
  proposer les journaux habilités du département du siège ;
- `code_depuis_nom` : collecte `jal_reference`, dont la source affiche des
  NOMS de départements (« Alpes de Haute-Provence »), pas des codes.

Cas particuliers gérés : Corse (codes postaux 20xxx -> 2A ou 2B), outre-mer
(97x/976 : 3 chiffres). Monaco (980xx) et les collectivités du Pacifique ne
sont pas des départements : None.
"""
import re
import unicodedata

DEPARTEMENTS: dict[str, str] = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence", "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes", "09": "Ariège", "10": "Aube",
    "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône", "14": "Calvados", "15": "Cantal",
    "16": "Charente", "17": "Charente-Maritime", "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud",
    "2B": "Haute-Corse", "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne",
    "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère",
    "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde", "34": "Hérault",
    "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère", "39": "Jura",
    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire", "44": "Loire-Atlantique",
    "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne", "48": "Lozère", "49": "Maine-et-Loire",
    "50": "Manche", "51": "Marne", "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle",
    "55": "Meuse", "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord",
    "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhône",
    "70": "Haute-Saône", "71": "Saône-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres",
    "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse",
    "85": "Vendée", "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne",
    "90": "Territoire de Belfort", "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion", "976": "Mayotte",
}

# Variantes de noms rencontrées dans les sources (clé déjà normalisée).
_ALIAS: dict[str, str] = {
    "REUNION": "974",
    "ILE DE LA REUNION": "974",
    "CORSE DU SUD": "2A",
    "HAUTE CORSE": "2B",
    "BELFORT": "90",
}


def _normaliser(nom: str) -> str:
    """Majuscules, sans accents, tirets/apostrophes -> espaces, espaces uniques."""
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFKD", nom) if not unicodedata.combining(c)
    )
    return re.sub(r"[\s\-'’]+", " ", sans_accents).upper().strip()


_CODE_PAR_NOM: dict[str, str] = {_normaliser(nom): code for code, nom in DEPARTEMENTS.items()} | _ALIAS


def code_depuis_nom(nom: str | None) -> str | None:
    """« Alpes de Haute-Provence » -> « 04 ». None si inconnu (jamais deviné)."""
    if not nom:
        return None
    cle = _normaliser(nom)
    # Certaines sources préfixent l'article (« La Réunion ») ou le code (« 75 - Paris »).
    cle = re.sub(r"^\d{2,3}\s+", "", cle)
    return _CODE_PAR_NOM.get(cle) or _CODE_PAR_NOM.get(re.sub(r"^(LA|LE|LES|L)\s+", "", cle))


def departement_depuis_code_postal(code_postal: str | None) -> str | None:
    """« 75011 » -> « 75 », « 20090 » -> « 2A », « 97400 » -> « 974 ». None si
    le code postal n'est pas un code français à 5 chiffres d'un département."""
    if not code_postal:
        return None
    cp = re.sub(r"\s", "", str(code_postal))
    if not re.fullmatch(r"\d{5}", cp):
        return None
    if cp.startswith("20"):
        # 200xx-201xx : Corse-du-Sud ; 202xx-206xx : Haute-Corse.
        return "2A" if cp[2] in "01" else "2B"
    if cp.startswith("97"):
        code = cp[:3]
        return code if code in DEPARTEMENTS else None
    code = cp[:2]
    return code if code in DEPARTEMENTS else None
