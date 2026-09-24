"""Tools du matching_copilot (volet conversationnel du matching_agent,

utilise par le copilot entrepreneur, agents/matching_agent/matching_copilot_
service.py) -- meme separation actee que compliance_agent_tools_service.py :
agents/ ne touche jamais la DB directement.

Lecture seule, aucune ecriture, et surtout : NE DECLENCHE JAMAIS un calcul de
matching (pas d'appel a match_chercheurs/run_matching depuis ces tools). Le
calcul reste une action explicite (bouton "Lancer/Relancer le matching",
voir chercheur_matching_orchestration_service.run_matching) : un appel Groq
de matching est plus lourd qu'une simple lecture (plusieurs tools, plusieurs
allers-retours, voir chercheur_matching_tools_service.py) et ne doit pas
partir automatiquement au fil d'une conversation libre. Ces tools ne font
que LIRE ce qui a deja ete calcule -- si rien n'existe encore pour un besoin,
le copilot doit orienter l'entrepreneur vers la page Matching plutot que de
lancer un calcul lui-meme.
"""
import logging
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.entrepreneur.services.project_service import get_owned_project
from backend.matching.models.research_need import ResearchNeed
from backend.matching.models.research_need_match import ResearchNeedMatch
from backend.shared.models.user import User

logger = logging.getLogger(__name__)


def _build_lire_besoins_recherche(db: Session, user: User, project_id: UUID) -> Callable[[], list[dict]]:
    def lire_besoins_recherche() -> list[dict]:
        """Renvoie les besoins scientifiques deja declares par ce projet

        (formulaire "Declarer un besoin", service 7.7.1) : identifiant,
        type ('probleme' ou 'expertise'), titre, description, statut
        ('ouvert' = un feed de matching est calcule pour ce besoin, 'ferme'
        = l'entrepreneur a trouve son chercheur ou abandonne). Liste vide si
        aucun besoin n'a encore ete declare -- dans ce cas, oriente
        l'entrepreneur vers le formulaire de declaration plutot que
        d'inventer un besoin.
        """
        logger.info("matching_copilot -- tool lire_besoins_recherche()")
        project = get_owned_project(db, user, project_id)
        needs = db.query(ResearchNeed).filter(ResearchNeed.project_id == project.id).all()
        return [
            {
                "id": str(n.id),
                "type_besoin": n.type_besoin,
                "titre": n.titre,
                "description": n.description,
                "statut": n.statut,
            }
            for n in needs
        ]

    return lire_besoins_recherche


def _build_lire_matches_existants(db: Session, user: User, project_id: UUID) -> Callable[[], list[dict]]:
    def lire_matches_existants() -> list[dict]:
        """Renvoie les recommandations de chercheurs DEJA calculees pour les

        besoins de ce projet (un element par besoin ayant deja un matching
        genere) : titre du besoin, synthese, et la liste des chercheurs
        recommandes (nom, rang, niveau de pertinence, deja marque "interesse"
        ou non). Ne calcule RIEN : si un besoin n'apparait pas ici, c'est
        qu'aucun matching n'a encore ete lance pour lui -- oriente alors
        l'entrepreneur vers le bouton "Lancer le matching" de la page
        Matching plutot que d'inventer des recommandations.
        """
        logger.info("matching_copilot -- tool lire_matches_existants()")
        project = get_owned_project(db, user, project_id)
        rows = (
            db.query(ResearchNeedMatch, ResearchNeed)
            .join(ResearchNeed, ResearchNeed.id == ResearchNeedMatch.research_need_id)
            .filter(ResearchNeed.project_id == project.id)
            .all()
        )
        return [
            {
                "need_id": str(need.id),
                "need_titre": need.titre,
                "synthese": match_row.synthese,
                "matches": [
                    {
                        "nom": m.get("nom"),
                        "rang": m.get("rang"),
                        "niveau_pertinence": m.get("niveau_pertinence"),
                        "interesse": m.get("interesse", False),
                    }
                    for m in match_row.matches
                ],
            }
            for match_row, need in rows
        ]

    return lire_matches_existants


def build_matching_copilot_tools(db: Session, user: User, project_id: UUID) -> list[Callable]:
    """Construit les 2 tools en lecture seule du matching_copilot, fermes sur

    (db, user, project_id) pour ce run precis. Pas de seen_source_ids/
    seen_chunks ici (contrairement a compliance_agent/administrative_agent) :
    ces tools ne font pas de recherche semantique dans un corpus de chunks,
    ils lisent des lignes structurees directement -- rien a verifier via le
    mecanisme d'ancrage (grounding_verification_service), qui ne s'applique
    qu'aux reponses appuyees sur des chunks de texte libre.
    """
    return [
        _build_lire_besoins_recherche(db, user, project_id),
        _build_lire_matches_existants(db, user, project_id),
    ]
