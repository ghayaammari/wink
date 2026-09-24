"""Tools du matching_investisseur_copilot (volet conversationnel de tout ce

qui touche le matching investissement cote entrepreneur, utilise par le
copilot entrepreneur, agents/matching_agent/matching_investisseur_copilot_
service.py) -- meme separation actee que matching_copilot_tools_service.py :
agents/ ne touche jamais la DB directement.

2 tools, couvrant les 2 sens du matching investissement qui concernent
l'entrepreneur :
- lire_offres_recommandees lit project_offer_matches -- le resultat DEJA
  CALCULE du matching_agent_startup (Startup -> Offres, service EPIC-06
  6.6.1, bouton "Visualiser les offres" cote entrepreneur, voir
  startup_offer_matching_orchestration_service.py) : les offres
  recommandees pour CE projet, et lesquelles sont deja marquees
  "interessantes" par l'entrepreneur lui-meme.
- lire_investisseurs_interesses lit investment_offer_matches -- l'autre
  sens (Investisseur -> Startup, matching_agent_investisseur), pour savoir
  si un investisseur a, de son cote, deja marque CE projet comme
  interessant.

Lecture seule, aucune ecriture, et surtout : NE DECLENCHE JAMAIS un calcul
de matching (ni matching_agent_startup ni matching_agent_investisseur) --
ces calculs restent des actions explicites (boutons "Visualiser les
offres"/"Visualiser" dedies), jamais declenches depuis cette conversation,
meme raisonnement que matching_copilot_tools_service.py.

Ne renvoie jamais l'email de contact ni le nom de l'investisseur : le
contact reste une action deliberee, pas une info glissee au fil d'une
conversation (service I.S.5 "Contact par email + tracking d'intérêt",
prevu mais pas encore construit) -- seuls le type d'investisseur et l'offre
elle-meme (secteurs cibles, montant) sont exposes, cote entrepreneur.
"""
import logging
from typing import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.entrepreneur.services.project_offer_match_service import get_result as get_offer_match_result
from backend.entrepreneur.services.project_service import get_owned_project
from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.models.investment_offer_match import InvestmentOfferMatch
from backend.investisseur.models.investor_profile import InvestorProfile
from backend.shared.models.user import User

logger = logging.getLogger(__name__)


def _build_lire_offres_recommandees(db: Session, project_id: UUID) -> Callable[[], list[dict]]:
    def lire_offres_recommandees() -> list[dict]:
        """Renvoie les offres d'investissement DEJA recommandees pour ce

        projet par le matching_agent_startup (declenche par le bouton
        "Visualiser les offres" de la page Investissement) : titre,
        montant et secteurs/stades cibles de l'offre, rang, niveau de
        pertinence, explication du match, et si l'entrepreneur l'a deja
        marquee "interessante". Liste vide si aucun matching n'a encore ete
        lance pour ce projet -- dans ce cas, oriente l'entrepreneur vers le
        bouton "Visualiser les offres" de la page Investissement plutot que
        d'inventer une recommandation.
        """
        logger.info("matching_investisseur_copilot -- tool lire_offres_recommandees()")
        row = get_offer_match_result(db, project_id)
        if row is None:
            return []
        return [
            {
                "offer_id": m.get("offer_id"),
                "rang": m.get("rang"),
                "niveau_pertinence": m.get("niveau_pertinence"),
                "explication": m.get("explication"),
                "interesse": m.get("interesse", False),
            }
            for m in row.matches
        ]

    return lire_offres_recommandees

def _build_lire_investisseurs_interesses(db: Session, project_id: UUID) -> Callable[[], list[dict]]:
    def lire_investisseurs_interesses() -> list[dict]:
        """Renvoie les offres d'investissement dont l'investisseur a marque

        CE projet comme "interessant" (etoile activee cote investisseur,
        apres avoir lance un matching sur son offre) : titre de l'offre,
        secteurs/montant cibles, type d'investisseur, niveau de pertinence
        et explication du match. Liste vide si aucun investisseur n'a
        encore marque d'interet -- dans ce cas, dis clairement qu'aucun
        investisseur n'a manifeste d'interet pour l'instant plutot que d'en
        inventer un. Ne contient jamais de coordonnees de contact (nom,
        email) : le contact reste une etape a part, pas encore construite.
        """
        logger.info("matching_investisseur_copilot -- tool lire_investisseurs_interesses()")
        rows = (
            db.query(InvestmentOfferMatch, InvestmentOffer, InvestorProfile)
            .join(InvestmentOffer, InvestmentOffer.id == InvestmentOfferMatch.investment_offer_id)
            .join(InvestorProfile, InvestorProfile.id == InvestmentOffer.investor_profile_id)
            .filter(
                # jsonb_array_elements sur `matches` -- pas d'equivalent ORM propre pour
                # "au moins un element de ce tableau JSONB a project_id=X et interesse=true"
                # (matches est un JSONB *liste*, pas une table associee), d'ou le SQL brut
                # plutot qu'une construction .filter() ORM alambiquee pour le meme resultat.
                text(
                    "EXISTS ("
                    "  SELECT 1 FROM jsonb_array_elements(investment_offer_matches.matches) elem"
                    "  WHERE elem->>'project_id' = :project_id"
                    "  AND (elem->>'interesse')::boolean IS TRUE"
                    ")"
                ).bindparams(project_id=str(project_id))
            )
            .all()
        )

        resultats: list[dict] = []
        for match_row, offer, investor in rows:
            match_entry = next(
                (
                    m
                    for m in match_row.matches
                    if m.get("project_id") == str(project_id) and m.get("interesse")
                ),
                None,
            )
            if match_entry is None:
                # Ne devrait pas arriver (le EXISTS ci-dessus garantit sa presence) --
                # filet de securite si le JSONB est un jour incoherent avec le SQL brut.
                continue
            resultats.append(
                {
                    "offer_titre": offer.titre,
                    "secteurs_cibles": offer.secteurs_cibles,
                    "montant_propose": offer.montant_propose,
                    "investor_type": investor.investor_type,
                    "niveau_pertinence": match_entry.get("niveau_pertinence"),
                    "explication": match_entry.get("explication"),
                }
            )
        return resultats

    return lire_investisseurs_interesses


def build_matching_investisseur_copilot_tools(db: Session, user: User, project_id: UUID) -> list[Callable]:
    """Construit les 2 tools en lecture seule du matching_investisseur_

    copilot, fermes sur (db, project_id) pour ce run precis. get_owned_project
    sert ici uniquement de controle d'autorisation (leve ForbiddenError si
    project_id n'appartient pas a `user`) -- les tools eux-memes ne font
    jamais confiance a un project_id fourni par l'agent, ils sont fermes sur
    celui deja verifie ici. Pas de seen_source_ids/seen_chunks (comme
    matching_copilot_tools_service.py) : lecture de lignes structurees, pas
    de recherche semantique, rien a verifier via l'ancrage.
    """
    get_owned_project(db, user, project_id)
    return [
        _build_lire_offres_recommandees(db, project_id),
        _build_lire_investisseurs_interesses(db, project_id),
    ]
