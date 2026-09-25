"""Rédaction du texte de l'annonce légale de constitution d'une SAS
(service 1.1.5). Fonction PURE : données déjà lues -> texte. Aucun accès base,
aucun LLM.

Pourquoi un modèle fixe et pas un LLM : l'art. R210-4 du Code de commerce
impose une liste fermée de mentions ; un LLM pourrait en oublier ou en
inventer, et une annonce publiée avec une erreur ne se corrige que par une
annonce rectificative payante. La relecture humaine (statut `genere`) reste
l'endroit où l'entrepreneur ajuste le texte (ex. résumer l'objet social).

Mentions (R210-4) -> ligne du texte :
  acte (usage, pas R210-4)   « Aux termes d'un acte sous seing privé… »
  1° dénomination + sigle     « Dénomination : »
  2° forme                    « Forme : »
  3° capital                  « Capital : »
  4° siège                    « Siège : »
  5° objet (sommairement)     « Objet : »
  6° durée                    « Durée : »
  8°/9° dirigeants            « Président : », « Directeur général : »
  10° greffe                  « Immatriculation au RCS de … »
  sociétés par actions        « Admission aux assemblées… », « Agrément : »
Non applicables à une SAS v1 : associés tenus indéfiniment (7°), capital
variable, commissaire aux comptes (absent du clausier des statuts).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from backend.shared.utils.formatting import formater_date, formater_montant

# Modalités de transmission des actions, déduites des statuts finalisés.
AGREMENT = "agrement"
CESSION_LIBRE = "libre"
RESTRICTIONS_SANS_AGREMENT = "restrictions_sans_agrement"

# Texte fidèle à l'Art. 28 des statuts Wink (`modalites_decisions_collectives`,
# texte fixe, sans variante) : « Chaque associé a le droit de participer à
# toute décision soit directement, soit par l'intermédiaire d'un mandataire ».
# Volontairement PAS « une action = une voix » : les statuts ne l'écrivent pas
# explicitement (point à faire confirmer juridiquement avant de l'ajouter).
PHRASE_ADMISSION_ASSEMBLEES = (
    "Admission aux assemblées et exercice du droit de vote : tout associé a le droit de "
    "participer aux décisions collectives, directement ou par l'intermédiaire d'un mandataire."
)


class DonneesAnnonceIncompletes(ValueError):
    """Une mention obligatoire manque. Ne devrait jamais arriver : la
    pré-validation bloque avant (`legal_announcement_prevalidation.py`). Levée
    plutôt qu'un texte à trous, jamais publiable."""


@dataclass(frozen=True)
class DirigeantAnnonce:
    """Personne physique : `nom` + `adresse`. Personne morale : `nom` =
    dénomination, `adresse` = siège, + champs PM optionnels."""
    nom: str
    adresse: str | None
    est_personne_morale: bool = False
    forme_juridique: str | None = None
    capital_social: Decimal | None = None
    lieu_immatriculation: str | None = None
    siren: str | None = None
    representant: str | None = None


@dataclass(frozen=True)
class DonneesAnnonce:
    date_acte: date | str
    lieu_acte: str
    denomination: str
    sigle: str | None
    unipersonnelle: bool
    siege: str
    objet_social: str
    duree_annees: int
    capital_social: Decimal
    greffe: str
    transmission_actions: str  # AGREMENT | CESSION_LIBRE | RESTRICTIONS_SANS_AGREMENT
    exceptions_agrement: str | None
    president: DirigeantAnnonce
    directeur_general: DirigeantAnnonce | None = None


def _sans_point_final(texte: str) -> str:
    return texte.strip().rstrip(".").strip()


def _verifier(d: DonneesAnnonce) -> None:
    manquants = [
        libelle
        for libelle, valeur in (
            ("date de l'acte", d.date_acte),
            ("lieu de l'acte", d.lieu_acte),
            ("dénomination", d.denomination),
            ("siège", d.siege),
            ("objet social", d.objet_social),
            ("durée", d.duree_annees),
            ("capital", d.capital_social),
            ("greffe", d.greffe),
            ("président", d.president and d.president.nom),
        )
        if valeur is None or (isinstance(valeur, str) and not valeur.strip())
    ]
    if d.transmission_actions not in (AGREMENT, CESSION_LIBRE, RESTRICTIONS_SANS_AGREMENT):
        manquants.append("modalité de transmission des actions")
    if manquants:
        raise DonneesAnnonceIncompletes("Mentions manquantes : " + ", ".join(manquants) + ".")


def _ligne_dirigeant(libelle: str, p: DirigeantAnnonce) -> str:
    if not p.est_personne_morale:
        adresse = f", demeurant {_sans_point_final(p.adresse)}" if p.adresse else ""
        return f"{libelle} : {p.nom.strip()}{adresse}."
    morceaux = [p.nom.strip()]
    if p.forme_juridique and p.capital_social is not None:
        morceaux.append(f"{p.forme_juridique} au capital de {formater_montant(p.capital_social)} euros")
    elif p.forme_juridique:
        morceaux.append(p.forme_juridique)
    if p.adresse:
        morceaux.append(f"dont le siège est {_sans_point_final(p.adresse)}")
    if p.lieu_immatriculation and p.siren:
        morceaux.append(f"immatriculée au RCS de {p.lieu_immatriculation} sous le numéro {p.siren}")
    if p.representant:
        morceaux.append(f"représentée par {p.representant}")
    return f"{libelle} : " + ", ".join(morceaux) + "."


def _ligne_transmission(d: DonneesAnnonce) -> str:
    if d.transmission_actions == CESSION_LIBRE:
        return "Transmission des actions : les actions sont librement cessibles."
    if d.transmission_actions == RESTRICTIONS_SANS_AGREMENT:
        return "Agrément : les statuts ne prévoient pas de clause d'agrément des cessions d'actions."
    ligne = "Agrément : les transferts d'actions sont soumis à l'agrément de la collectivité des associés"
    if d.exceptions_agrement and d.exceptions_agrement.strip():
        ligne += f", à l'exception des cas suivants : {_sans_point_final(d.exceptions_agrement)}"
    return ligne + "."


def generer_texte_annonce(d: DonneesAnnonce) -> str:
    """Texte complet de l'avis de constitution, une mention par ligne."""
    _verifier(d)
    forme = "société par actions simplifiée" + (" unipersonnelle" if d.unipersonnelle else "")
    denomination = d.denomination.strip() + (f". Sigle : {d.sigle.strip()}" if d.sigle and d.sigle.strip() else "")
    lignes = [
        f"Aux termes d'un acte sous seing privé en date du {formater_date(d.date_acte)} à {d.lieu_acte.strip()}, "
        "il a été constitué une société présentant les caractéristiques suivantes :",
        f"Forme : {forme}.",
        f"Dénomination : {denomination}.",
        f"Siège : {_sans_point_final(d.siege)}.",
        f"Objet : {_sans_point_final(d.objet_social)}.",
        f"Durée : {d.duree_annees} ans à compter de son immatriculation au Registre du commerce et des sociétés.",
        f"Capital : {formater_montant(d.capital_social)} euros.",
        PHRASE_ADMISSION_ASSEMBLEES,
        _ligne_transmission(d),
        _ligne_dirigeant("Président", d.president),
    ]
    if d.directeur_general is not None:
        lignes.append(_ligne_dirigeant("Directeur général", d.directeur_general))
    lignes.append(f"Immatriculation au Registre du commerce et des sociétés de {d.greffe.strip()}.")
    return "\n".join(lignes)
