"""Petites fonctions partagées par les tools (lecture des valeurs saisies)."""
from datetime import date
from decimal import Decimal, InvalidOperation

from agents.document_generation_validation.contexte import SectionContexte
from agents.document_generation_validation.probleme import CIBLE_SECTION, Probleme


def nombre(valeur) -> Decimal | None:
    if valeur is None or isinstance(valeur, (dict, list, bool)):
        return None
    try:
        return Decimal(str(valeur).replace(" ", "").replace("\u00a0", "").replace(",", "."))
    except InvalidOperation:
        return None


def date_iso(valeur) -> date | None:
    try:
        return date.fromisoformat(str(valeur).strip()) if valeur else None
    except ValueError:
        return None


def euros(v: Decimal) -> str:
    """20000 -> « 20 000 € », 1250.5 -> « 1 250,50 € »."""
    v = v.quantize(Decimal("0.01"))
    entier, _, decimales = f"{v:.2f}".partition(".")
    signe = "-" if entier.startswith("-") else ""
    chiffres = entier.lstrip("-")
    groupes = []
    while chiffres:
        groupes.insert(0, chiffres[-3:])
        chiffres = chiffres[:-3]
    texte = signe + "\u00a0".join(groupes)
    return f"{texte},{decimales}\u00a0€" if decimales != "00" else f"{texte}\u00a0€"


def jj_mm_aaaa(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def probleme_section(section: SectionContexte, **kwargs) -> Probleme:
    """Problème rattaché à une section du parcours (lien « Corriger → »)."""
    return Probleme(cible_type=CIBLE_SECTION, cible=section.code_section, cible_libelle=section.libelle, **kwargs)
