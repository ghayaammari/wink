"""Tools du matching_agent_startup (agents/matching_agent/startup_offer_

matching_service.py) qui ont besoin d'une Session DB -- même séparation
actée que investisseur_matching_tools_service.py : `agents/` ne touche
jamais la DB directement, ces fonctions sont de simples fermetures sur
(db), injectées à l'agent au moment de l'appel.

Sens INVERSE de investisseur_matching_tools_service.py : celui-là liste les
STARTUPS candidates pour l'offre d'un investisseur ; celui-ci liste les
OFFRES ouvertes pour LE PROJET d'un entrepreneur. C'est l'agent qui décide,
selon la situation, s'il a besoin d'approfondir une offre précise avant de
trancher (lire_offre_detail) -- jamais par défaut.

Lecture seule, aucune écriture : la persistance du résultat reste toujours
du ressort de startup_offer_matching_orchestration_service.run_matching
(upsert_result), jamais de l'agent.

Même pacing que investisseur_matching_tools_service.py (_PACING_SECONDS) :
même moteur Groq, même plafond 8000 TPM/organisation.
"""
import time
from functools import wraps
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.investisseur.models.investment_offer import InvestmentOffer
from backend.investisseur.models.investor_profile import InvestorProfile

_PACING_SECONDS = 25
_MAX_CHARS_TEXTE_RETOURNE = 300


def _tronquer_texte(texte: str | None, max_chars: int = _MAX_CHARS_TEXTE_RETOURNE) -> str | None:
    if texte is None or len(texte) <= max_chars:
        return texte
    return texte[:max_chars] + " [...]"


def _avec_pacing(fn: Callable) -> Callable:
    """Même principe que _avec_pacing côté investisseur_matching_tools_

    service.py -- voir sa docstring (CORRECTIF du 23/09/2026, v4)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        time.sleep(_PACING_SECONDS)
        return result

    return wrapper


def _build_lister_offres_disponibles(db: Session, seen_offer_ids: list[str]) -> Callable[[], list[dict]]:
    def lister_offres_disponibles() -> list[dict]:
        """Offres d'investissement ouvertes, avec résumé déjà inclus."""
        rows = (
            db.query(InvestmentOffer, InvestorProfile)
            .join(InvestorProfile, InvestorProfile.id == InvestmentOffer.investor_profile_id)
            .filter(InvestmentOffer.statut == "ouvert")
            .all()
        )
        seen_offer_ids.extend(str(offer.id) for offer, _ in rows)

        return [
            {
                "offer_id": str(offer.id),
                "titre": offer.titre,
                "description": _tronquer_texte(offer.description),
                "montant_propose": offer.montant_propose,
                "secteurs_cibles": offer.secteurs_cibles,
                "stades_cibles": offer.stades_cibles,
                "investor_type": investor.investor_type,
            }
            for offer, investor in rows
        ]

    return lister_offres_disponibles


def _build_lire_offre_detail(db: Session) -> Callable[[str], dict]:
    def lire_offre_detail(offer_id: str) -> dict:
        """Description complète (non tronquée) d'une offre précise, avec la

        thèse d'investissement complète de l'investisseur."""
        row = (
            db.query(InvestmentOffer, InvestorProfile)
            .join(InvestorProfile, InvestorProfile.id == InvestmentOffer.investor_profile_id)
            .filter(InvestmentOffer.id == offer_id)
            .first()
        )
        if row is None:
            return {"erreur": "offre introuvable"}
        offer, investor = row
        return {
            "description": offer.description,
            "investment_thesis": investor.investment_thesis,
        }

    return lire_offre_detail


def build_startup_offer_matching_tools(db: Session, seen_offer_ids: list[str]) -> list[Callable]:
    """Construit les 2 tools du matching_agent_startup -- voir agents/

    matching_agent/startup_offer_matching_service.py pour la définition de
    l'agent lui-même. `seen_offer_ids` (liste vide fournie par l'appelant)
    est remplie par lister_offres_disponibles pendant le run --
    startup_offer_matching_orchestration_service.run_matching s'en sert
    ensuite pour écarter tout offer_id halluciné par l'agent."""
    return [
        _avec_pacing(_build_lister_offres_disponibles(db, seen_offer_ids)),
        _avec_pacing(_build_lire_offre_detail(db)),
    ]
