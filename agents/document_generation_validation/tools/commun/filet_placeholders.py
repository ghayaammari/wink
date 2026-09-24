"""Tool ⑥ (commun) — filet de sécurité final : aucun texte « (… non
renseigné) » ni « (… non désigné …) » ne doit rester dans le document
assemblé.

Lancé en DERNIER : il attrape ce que les autres tools n'ont pas prévu. Un
trou déjà signalé par un tool précédent sur la même cible n'est pas répété.

« (article non inclus…) » n'est volontairement PAS signalé (décision
utilisateur 25/09/2026) : c'est un renvoi de notre clausier, pas une erreur
de l'utilisateur ; le tool `correction_renvois` corrige le texte quand il
le peut, sinon il reste tel quel.
"""
import re

from agents.document_generation_validation.contexte import ContexteValidation
from agents.document_generation_validation.probleme import (
    CIBLE_PAGE,
    CIBLE_SECTION,
    PAGE_DIRIGEANTS,
    PAGE_EQUIPE_CAPITAL,
    PAGE_INFORMATIONS_LEGALES,
    Probleme,
)

NOM = "filet_placeholders"
LIBELLE = "Aucun texte manquant dans le document"

TROU_RE = re.compile(r"\((?:[^()]*\bnon (?:renseigné|désigné)e?s?\b[^()]*)\)")
_NON_RENSEIGNE_RE = re.compile(r"\s*\bnon (?:renseigné|désigné)e?s?\b.*$")

# Sections dont le contenu automatique vient d'une page du projet.
_SECTIONS_DIRIGEANTS_PREFIXES = ("nomination_", "mandat_actes", "cloture_annexe_mandat")
_SECTIONS_EQUIPE_CAPITAL = {
    "identification_des_parties",
    "apports_numeraire_liberation",
    "apport_nature_identite",
    "evaluation_apports_nature",
    "apports_industrie",
}
_TITRES_PAGES = {
    PAGE_DIRIGEANTS: "Dirigeants",
    PAGE_EQUIPE_CAPITAL: "Équipe & capital",
    PAGE_INFORMATIONS_LEGALES: "Informations légales",
}


def _cible(contexte: ContexteValidation, code_section: str | None, trou: str) -> tuple[str, str, str]:
    """(type, cible, libellé de l'emplacement dans les statuts)."""
    section = contexte.section(code_section) if code_section else None
    ou = section.libelle if section else "En-tête des statuts"
    if "page Dirigeants" in trou or (code_section or "").startswith(_SECTIONS_DIRIGEANTS_PREFIXES):
        return CIBLE_PAGE, PAGE_DIRIGEANTS, ou
    if code_section in _SECTIONS_EQUIPE_CAPITAL:
        return CIBLE_PAGE, PAGE_EQUIPE_CAPITAL, ou
    if section is not None and section.saisie_utilisateur:
        return CIBLE_SECTION, section.code_section, ou
    # Section remplie automatiquement hors dirigeants / associés : ses
    # données viennent du profil juridique du projet.
    return CIBLE_PAGE, PAGE_INFORMATIONS_LEGALES, ou


def _nom_du_champ(trou: str) -> str:
    """« (durée non renseignée) » -> « Durée »."""
    nom = _NON_RENSEIGNE_RE.sub("", trou.strip("()")).strip(" —-")
    return (nom[:1].upper() + nom[1:]) if nom else "Information"


def executer(contexte: ContexteValidation, precedents: list[Probleme]) -> list[Probleme]:
    deja = {(p.cible_type, p.cible) for p in precedents}
    vus: set[tuple] = set()
    problemes: list[Probleme] = []
    for bloc in contexte.blocs:
        for trou in TROU_RE.findall(bloc.texte):
            cible_type, cible, ou = _cible(contexte, bloc.code_section, trou)
            cle = (cible_type, cible, trou)
            if cle in vus or (cible_type, cible) in deja:
                continue
            vus.add(cle)
            champ = _nom_du_champ(trou)
            lieu = f"la page {_TITRES_PAGES[cible]}" if cible_type == CIBLE_PAGE else "cette section"
            problemes.append(
                Probleme(
                    code="document_texte_manquant",
                    message_court=f"Information manquante : {champ.lower()}",
                    champ=champ,
                    valeur_actuelle="Non renseigné",
                    correction_proposee=f"Renseignez « {champ.lower()} » dans {lieu}.",
                    message=f"Sans cette information, les statuts afficheraient « {trou} » à cet endroit.",
                    cible_type=cible_type,
                    cible=cible,
                    cible_libelle=ou,
                )
            )
    return problemes
