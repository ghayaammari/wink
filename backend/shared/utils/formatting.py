"""Mise en forme des valeurs pour les documents juridiques (format français).

Module partagé (décision utilisateur, 25/09/2026) : utilisé par la génération
des statuts (1.1.4) et de l'annonce légale (1.1.5). Fonctions pures, sans
accès base ni dépendance à un service — c'est ce qui permet de les partager
sans créer de couplage entre services.

Historique : `formater_montant` vivait dans
`entrepreneur/services/document_renderer_base.py` et `formater_siege_social`
(ex-`_formater_siege_social`, privée) dans `document_generation_service.py`.
Les deux modules réimportent maintenant d'ici (même nom), aucun appelant
existant n'a changé.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def formater_montant(valeur) -> str:
    """Montant ou nombre au format français : 20000.00 -> « 20 000 »,
    1250.5 -> « 1 250,50 » (espaces insécables : un nombre n'est jamais coupé
    en fin de ligne). Une valeur non numérique (placeholder « (… non
    renseigné) ») est rendue telle quelle."""
    try:
        v = Decimal(str(valeur).replace(" ", "").replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return str(valeur)
    if not v.is_finite():
        return str(valeur)
    v = v.quantize(Decimal("0.01"))
    entier, _, decimales = f"{abs(v):.2f}".partition(".")
    groupes = []
    while entier:
        groupes.insert(0, entier[-3:])
        entier = entier[:-3]
    texte = ("-" if v < 0 else "") + " ".join(groupes)
    return texte if decimales == "00" else f"{texte},{decimales}"


def formater_siege_social(adresse: dict | None) -> str | None:
    """Formate une adresse JSONB libre (`ProjectLegalProfile.registered_address`)
    en une chaîne. Champs attendus, tous optionnels : `ligne1`, `ligne2`,
    `code_postal`, `ville`. Les champs absents sont sautés (jamais de virgule
    vide ni de « None ») ; None si rien d'exploitable."""
    if not adresse:
        return None
    parts = [adresse.get("ligne1"), adresse.get("ligne2")]
    ville = " ".join(p for p in (adresse.get("code_postal"), adresse.get("ville")) if p)
    if ville:
        parts.append(ville)
    parts = [p for p in parts if p]
    return ", ".join(parts) if parts else None


def formater_date(valeur) -> str | None:
    """Date au format JJ/MM/AAAA. Accepte un `date`/`datetime`, une chaîne ISO
    (« 2026-10-01 ») ou une chaîne déjà au format JJ/MM/AAAA (rendue telle
    quelle). None si vide ; toute autre chaîne est rendue telle quelle (on ne
    devine jamais une date)."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, datetime):
        return valeur.strftime("%d/%m/%Y")
    if isinstance(valeur, date):
        return valeur.strftime("%d/%m/%Y")
    texte = str(valeur).strip()
    try:
        return date.fromisoformat(texte[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return texte
