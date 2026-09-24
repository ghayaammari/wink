"""Pré-validation de l'annonce légale (service 1.1.5) : liste les problèmes
BLOQUANTS avant génération, et les avertissements NON bloquants.

Même format que `statuts_sas_prevalidation.py` (`{code, message, page}`) : le
frontend réutilise le même écran « Compléter → » avec lien vers la page où
corriger. Fonction pure : reçoit un `ContexteAnnonce` déjà lu par le service
(aucun accès base ici), donc testable sans base.

Décision « option 2 » (24/09/2026) : l'annonce lit les tables du projet
(source unique), et AVERTIT si elles ont changé après la finalisation des
statuts — l'annonce doit décrire les statuts signés.
Limite connue : une SUPPRESSION d'associé ou de dirigeant ne change aucun
`updated_at` restant -> non détectée par cet avertissement.
"""
from dataclasses import dataclass
from datetime import datetime

from backend.entrepreneur.services.statuts_sas_prevalidation import (
    FORME_JURIDIQUE_ATTENDUE,
    PAGE_DIRIGEANTS,
    PAGE_INFORMATIONS_LEGALES,
)

PAGE_STATUTS = "statuts"
PAGE_ANNONCE = "annonce_legale"

# Au-delà, l'objet social n'est probablement pas « indiqué sommairement »
# (R210-4, 5°) : simple avertissement, l'entrepreneur résume à la relecture.
LONGUEUR_OBJET_SOCIAL_CONSEILLEE = 400


@dataclass
class IdentiteLue:
    """Identité d'un dirigeant telle que lue en base, avant mise en forme."""
    nom: str | None
    adresse: str | None
    page: str  # où la corriger : dirigeants (non associé) ou equipe_capital (associé)


@dataclass
class ContexteAnnonce:
    statuts_finalises_le: datetime | None
    forme_juridique: str | None
    denomination: str | None
    objet_social: str | None
    duree_societe: int | None
    capital_social: object | None
    greffe: str | None
    siege_formate: str | None
    departement: str | None
    date_acte: str | None
    lieu_acte: str | None
    transmission_actions: str | None
    president: IdentiteLue | None
    directeur_general: IdentiteLue | None
    # Dernière modification des données du projet reprises dans l'annonce.
    donnees_modifiees_le: datetime | None = None
    # Annonce déjà générée (None sinon).
    annonce_generee_le: datetime | None = None


def _probleme(code: str, message: str, page: str) -> dict:
    return {"code": code, "message": message, "page": page}


def _vide(valeur) -> bool:
    return valeur is None or (isinstance(valeur, str) and not valeur.strip())


def _verifier_identite(identite: IdentiteLue | None, role: str, code: str) -> list[dict]:
    if identite is None:
        return []
    problemes = []
    if _vide(identite.nom):
        problemes.append(_probleme(f"{code}_nom", f"Le nom du {role} n'est pas renseigné.", identite.page))
    if _vide(identite.adresse):
        problemes.append(
            _probleme(f"{code}_adresse", f"L'adresse (ou le siège) du {role} n'est pas renseignée.", identite.page)
        )
    return problemes


def prevalider_annonce(ctx: ContexteAnnonce) -> list[dict]:
    """Problèmes bloquants (liste vide = on peut générer)."""
    if ctx.statuts_finalises_le is None:
        # Tout le reste dépend des statuts signés : inutile d'empiler d'autres messages.
        return [
            _probleme(
                "statuts_non_finalises",
                "Finalisez d'abord vos statuts : l'annonce légale résume les statuts signés.",
                PAGE_STATUTS,
            )
        ]

    problemes = []
    if ctx.forme_juridique != FORME_JURIDIQUE_ATTENDUE:
        problemes.append(
            _probleme(
                "forme_non_supportee",
                "Seule la SAS est prise en charge pour l'instant (forme juridique : « SAS »).",
                PAGE_INFORMATIONS_LEGALES,
            )
        )
    for valeur, code, libelle in (
        (ctx.denomination, "denomination", "la dénomination sociale"),
        (ctx.objet_social, "objet_social", "l'objet social"),
        (ctx.duree_societe, "duree_societe", "la durée de la société"),
        (ctx.capital_social, "capital_social", "le capital social"),
        (ctx.greffe, "greffe", "la ville du greffe (RCS)"),
        (ctx.siege_formate, "siege", "l'adresse du siège"),
    ):
        if _vide(valeur):
            problemes.append(_probleme(code, f"Renseignez {libelle}.", PAGE_INFORMATIONS_LEGALES))
    if not _vide(ctx.siege_formate) and ctx.departement is None:
        problemes.append(
            _probleme(
                "code_postal_siege",
                "Le code postal du siège est absent ou invalide : impossible de trouver les journaux habilités.",
                PAGE_INFORMATIONS_LEGALES,
            )
        )
    if _vide(ctx.date_acte) or _vide(ctx.lieu_acte):
        problemes.append(
            _probleme(
                "date_lieu_signature",
                "Le lieu et la date de signature des statuts sont introuvables : régénérez vos statuts.",
                PAGE_STATUTS,
            )
        )
    if ctx.transmission_actions is None:
        problemes.append(
            _probleme(
                "transmission_actions",
                "Les règles de cession des actions sont introuvables dans vos statuts : régénérez-les.",
                PAGE_STATUTS,
            )
        )
    if ctx.president is None:
        problemes.append(_probleme("president", "Désignez le Président de la société.", PAGE_DIRIGEANTS))
    problemes += _verifier_identite(ctx.president, "Président", "president")
    problemes += _verifier_identite(ctx.directeur_general, "Directeur général", "directeur_general")
    return problemes


def avertissements_annonce(ctx: ContexteAnnonce) -> list[dict]:
    """Points NON bloquants à signaler à l'entrepreneur."""
    avertissements = []
    if (
        ctx.statuts_finalises_le is not None
        and ctx.donnees_modifiees_le is not None
        and ctx.donnees_modifiees_le > ctx.statuts_finalises_le
    ):
        avertissements.append(
            _probleme(
                "donnees_modifiees_depuis_statuts",
                "Vos informations ont changé après la génération de vos statuts : l'annonce doit décrire les "
                "statuts signés. Régénérez vos statuts si ce changement doit y figurer.",
                PAGE_STATUTS,
            )
        )
    if (
        ctx.annonce_generee_le is not None
        and ctx.donnees_modifiees_le is not None
        and ctx.donnees_modifiees_le > ctx.annonce_generee_le
    ):
        avertissements.append(
            _probleme(
                "annonce_a_regenerer",
                "Vos informations ont changé depuis la génération de l'annonce : régénérez-la avant de la publier.",
                PAGE_ANNONCE,
            )
        )
    if ctx.objet_social and len(ctx.objet_social) > LONGUEUR_OBJET_SOCIAL_CONSEILLEE:
        avertissements.append(
            _probleme(
                "objet_social_long",
                "L'objet social doit être « indiqué sommairement » dans l'annonce (art. R210-4) : "
                "pensez à le résumer à la relecture.",
                PAGE_ANNONCE,
            )
        )
    return avertissements
