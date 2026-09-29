"""Tools du matching_agent (agents/matching_agent/chercheur_matching_
service.py) qui ont besoin d'une Session DB — même séparation actée pour
compliance_agent_tools_service.py : `agents/` ne touche jamais la DB
directement, ces fonctions sont de simples fermetures sur (db, need),
injectées à l'agent au moment de l'appel.

Lecture seule, aucune écriture : la persistance du résultat reste toujours
du ressort de chercheur_matching_orchestration_service.run_matching
(upsert_result), jamais de l'agent.

4 tools (pas 6, voir CORRECTIF v3 ci-dessous), pensés pour laisser l'agent
choisir lui-même sa profondeur de lecture au-delà du cas par défaut
(demande explicite du produit le 22/09/2026 — "il raisonne quel tool
utiliser") : lister_chercheurs_disponibles (inclut déjà les résumés, voir
v3), puis 3 tools de fallback (lire_expertises_passees,
lister_travaux_confirmes, lire_travail_detail) pour approfondir seulement
quand nécessaire.

CORRECTIF du 23/09/2026 (v2) -- 429 répétés en usage réel malgré la
troncature des textes retournés (v1, voir _tronquer_texte) : cause
principale identifiée après coup, le poids FIXE des schémas de tools (nom +
description + paramètres), renvoyé à CHAQUE étape de la boucle ReAct que le
tool soit appelé ou non. Corrigé en réduisant chaque docstring de fonction
(= la description envoyée au modèle) à 1 phrase courte ; la justification
produit complète reste en commentaire au-dessus de chaque _build_*, jamais
transmise à l'API.

CORRECTIF du 23/09/2026 (v3) -- v2 n'a pas suffi : le vrai goulot n'était
pas la taille de chaque appel mais leur NOMBRE. Avec 6 tools, le chemin par
défaut (lire_besoin, puis lister_chercheurs_disponibles, puis UN appel
lire_expertise_et_travaux_summary PAR chercheur) demandait déjà 4-5 allers-
retours LLM avant même un premier approfondissement -- largement assez pour
dépasser 8000 TPM/org en quelques secondes, quelle que soit la taille de
chaque message. Deux tools supprimés :
- lire_besoin : le besoin est maintenant passé directement dans le message
  de tâche (voir agents/matching_agent/chercheur_matching_service.py,
  match_chercheurs(tools, besoin)) -- un appel de moins, l'info était de
  toute façon toujours nécessaire au premier tour.
- lire_expertise_et_travaux_summary : fusionné DANS
  lister_chercheurs_disponibles, qui renvoie déjà les résumés de chaque
  candidat (simples colonnes de profil, aucun coût DB supplémentaire à les
  inclure) -- élimine 1 appel PAR chercheur pour le cas par défaut. Les 3
  tools de fallback restent séparés : eux sont vraiment optionnels, appelés
  seulement quand un résumé est absent ou insuffisant.
"""
import time
from functools import wraps
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.models.researcher_past_expertise import ResearcherPastExpertise
from backend.chercheur.models.researcher_profile import ResearcherProfile
from backend.matching.models.research_need import ResearchNeed
from backend.matching.models.research_need_match import ResearchNeedMatch
from backend.shared.models.user import User

_CONFIRMED = "confirmed"

# Troncature des textes longs retournés par un tool (v1 du CORRECTIF du
# 23/09/2026). Gardée en complément de v3 (moins d'appels) : moins de poids
# cumulé par étape reste utile pour les tools de fallback qui restent.
_MAX_CHARS_TEXTE_RETOURNE = 300


def _tronquer_texte(texte: str | None, max_chars: int = _MAX_CHARS_TEXTE_RETOURNE) -> str | None:
    """Coupe un texte trop long avant de le renvoyer au modèle."""
    if texte is None or len(texte) <= max_chars:
        return texte
    return texte[:max_chars] + " [...]"


# CORRECTIF du 23/09/2026 (v4) -- v3 (moins de tools/allers-retours) n'a
# pas suffi non plus : vérifié via la doc Groq, "Rate limits apply at the
# organization level, not individual users" -- les 3 clés du pool
# (key_pool.py) partagent donc TOUTES le même compteur si elles viennent du
# même compte Groq, ce qui rend leur rotation inutile contre ce plafond
# précis (elle reste utile pour d'autres erreurs 429 isolées, ailleurs).
# Le plafond (8000 TPM) est une fenêtre GLISSANTE d'une minute : si les
# étapes de la boucle ReAct se suivent en quelques secondes (cas actuel),
# leurs coûts s'additionnent tous dans la même fenêtre. En espaçant chaque
# appel d'outil de _PACING_SECONDS, les tokens des appels les plus anciens
# ont le temps de sortir de la fenêtre avant le suivant -- même agent,
# mêmes tools, juste plus lent (un run complet peut prendre 1-2 minutes au
# lieu de quelques secondes). Décision produit du 23/09/2026 (plutôt que
# de créer des comptes Groq séparés ou de simplifier l'agent).
_PACING_SECONDS = 25


def _avec_pacing(fn: Callable) -> Callable:
    """Enveloppe un tool pour marquer une pause après son exécution --

    retarde le prochain appel LLM de la boucle ReAct d'autant (voir
    CORRECTIF v4 ci-dessus). `@wraps` préserve nom/docstring/signature du
    tool d'origine, dont LangChain a besoin pour construire son schéma."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        time.sleep(_PACING_SECONDS)
        return result

    return wrapper


def _confirmed_field(db: Session, entity_type: str, entity_id: UUID, field_name: str) -> str | None:
    """Ne lit que la version confirmée d'un champ polymorphe

    (researcher_field_values) -- jamais une version encore
    pending_confirmation, pas fiable pour une recommandation transmise à
    un tiers (même principe que _get_confirmed_paper_summary,
    researcher_summary_service.py)."""
    row = (
        db.query(ResearcherFieldValue)
        .filter_by(entity_type=entity_type, entity_id=entity_id, field_name=field_name, validation_status=_CONFIRMED)
        .first()
    )
    return row.field_value if row else None


# Pool de candidats, résumés inclus directement (voir CORRECTIF v3) --
# un seul appel couvre tout le cas par défaut, plus besoin d'un aller-
# retour par chercheur pour ses résumés.
def _build_lister_chercheurs_disponibles(db: Session, seen_researcher_ids: list[str]) -> Callable[[], list[dict]]:
    def lister_chercheurs_disponibles() -> list[dict]:
        """Chercheurs candidats, avec affiliation, domaines et résumés."""
        rows = (
            db.query(ResearcherProfile, User)
            .join(User, User.id == ResearcherProfile.user_id)
            .filter(ResearcherProfile.profile_completion == "complet")
            .all()
        )
        seen_researcher_ids.extend(str(profile.id) for profile, _ in rows)
        return [
            {
                "researcher_profile_id": str(profile.id),
                "nom": f"{u.first_name} {u.last_name}".strip(),
                "affiliation": profile.affiliation,
                "research_domains": profile.research_domains,
                "expertise_summary": _tronquer_texte(profile.expertise_summary),
                "research_work_summary": _tronquer_texte(profile.research_work_summary),
            }
            for profile, u in rows
        ]

    return lister_chercheurs_disponibles


# Fallback si expertise_summary est absent (`null`), ou si le besoin porte
# sur un point précis (type de mission, domaine) qu'un résumé général ne
# détaille pas assez.
def _build_lire_expertises_passees(db: Session) -> Callable[[str], list[dict]]:
    def lire_expertises_passees(researcher_profile_id: str) -> list[dict]:
        """Missions/expertises passées brutes d'un chercheur."""
        rows = db.query(ResearcherPastExpertise).filter_by(researcher_profile_id=researcher_profile_id).all()
        return [
            {
                "organization_name": e.organization_name,
                "domain": e.domain,
                "mission_type": e.mission_type,
                "period_label": e.period_label,
                "description": _tronquer_texte(e.description),
            }
            for e in rows
        ]

    return lire_expertises_passees


# Fallback si research_work_summary est absent ; sert aussi à repérer l'id
# d'un travail précis à approfondir avec lire_travail_detail. Ignore les
# travaux encore pending_confirmation (pas assez fiables pour une
# recommandation transmise à un tiers).
def _build_lister_travaux_confirmes(db: Session) -> Callable[[str], list[dict]]:
    def lister_travaux_confirmes(researcher_profile_id: str) -> list[dict]:
        """Travaux confirmés d'un chercheur (titre, type, domaines)."""
        works = (
            db.query(ResearchWork)
            .filter_by(researcher_profile_id=researcher_profile_id, validation_status=_CONFIRMED)
            .all()
        )
        return [
            {
                "research_work_id": str(w.id),
                "title": w.title,
                "publication_type": w.publication_type,
                "application_domains": _confirmed_field(db, "research_work", w.id, "application_domains"),
            }
            for w in works
        ]

    return lister_travaux_confirmes


# Dernier niveau de détail : UN travail précis (repéré via
# lister_travaux_confirmes), pour trancher un point très spécifique qu'un
# titre ou un résumé global ne permettent pas de vérifier. Ne pas appeler
# sans savoir déjà quel travail regarder.
def _build_lire_travail_detail(db: Session) -> Callable[[str], dict]:
    def lire_travail_detail(research_work_id: str) -> dict:
        """Détail complet d'un travail précis (résumé, méthode, résultats)."""
        work = db.query(ResearchWork).filter_by(id=research_work_id).first()
        if work is None:
            return {"erreur": "travail introuvable"}
        return {
            "title": work.title,
            "abstract": _tronquer_texte(work.abstract),
            "venue": work.venue,
            "paper_summary": _tronquer_texte(_confirmed_field(db, "research_work", work.id, "paper_summary")),
            "methodology": _tronquer_texte(_confirmed_field(db, "research_work", work.id, "methodology")),
            "key_findings": _tronquer_texte(_confirmed_field(db, "research_work", work.id, "key_findings")),
            "application_domains": _confirmed_field(db, "research_work", work.id, "application_domains"),
        }

    return lire_travail_detail


def build_voir_resultat_matching_chercheur_tool(db: Session, project_id: UUID) -> Callable[[], dict]:
    """Ferme voir_resultat_matching_chercheur sur (db, project_id) -- a

    l'usage exclusif du copilot conversationnel (voir copilot_service.py),
    jamais de match_chercheurs lui-meme (build_matching_agent_tools
    ci-dessous), qui n'a aucun usage pour un resultat precedent pendant son
    propre calcul one-shot declenche par le bouton "Lancer le matching"."""

    def voir_resultat_matching_chercheur() -> dict:
        """Besoins deja declares par ce projet et, pour chacun, le resultat

        DEJA CALCULE du matching avec des chercheurs (synthese, chercheurs
        recommandes avec rang, niveau de pertinence, EXPLICATION du match,
        et s'ils sont deja marques "interesse"). Ne calcule RIEN -- un
        besoin sans matching associe a une liste de recommandations vide.
        """
        needs = db.query(ResearchNeed).filter(ResearchNeed.project_id == project_id).all()
        matches_par_besoin = {
            m.research_need_id: m
            for m in db.query(ResearchNeedMatch)
            .filter(ResearchNeedMatch.research_need_id.in_([n.id for n in needs]))
            .all()
        }
        return {
            "besoins": [
                {
                    "id": str(n.id),
                    "type_besoin": n.type_besoin,
                    "titre": n.titre,
                    "description": n.description,
                    "statut": n.statut,
                    "synthese": matches_par_besoin[n.id].synthese if n.id in matches_par_besoin else None,
                    "recommandations": [
                        {
                            "nom": rec.get("nom"),
                            "rang": rec.get("rang"),
                            "niveau_pertinence": rec.get("niveau_pertinence"),
                            "explication": rec.get("explication"),
                            "interesse": rec.get("interesse", False),
                        }
                        for rec in (matches_par_besoin[n.id].matches if n.id in matches_par_besoin else [])
                    ],
                }
                for n in needs
            ]
        }

    return voir_resultat_matching_chercheur


def build_matching_agent_tools(db: Session, seen_researcher_ids: list[str]) -> list[Callable]:
    """Construit les 4 tools du matching_agent (voir CORRECTIF v3 dans la

    docstring de module pour pourquoi 4 et pas 6) -- voir agents/
    matching_agent/chercheur_matching_service.py pour la définition de
    l'agent lui-même (system prompt, schéma de sortie), qui reste sans
    accès DB direct. Ne prend plus `user`/`need` : le besoin est passé
    directement dans le message de tâche (plus de tool lire_besoin), et
    aucun autre tool n'a besoin de vérifier une propriété -- le matching
    lit des données chercheur, cross-acteurs par nature.

    `seen_researcher_ids` (liste vide fournie par l'appelant) est remplie
    par lister_chercheurs_disponibles pendant le run —
    chercheur_matching_orchestration_service.run_matching s'en sert ensuite
    pour écarter tout researcher_profile_id halluciné par l'agent (même
    principe que seen_source_ids côté compliance_agent_tools_service.py)."""
    return [
        _avec_pacing(_build_lister_chercheurs_disponibles(db, seen_researcher_ids)),
        _avec_pacing(_build_lire_expertises_passees(db)),
        _avec_pacing(_build_lister_travaux_confirmes(db)),
        _avec_pacing(_build_lire_travail_detail(db)),
    ]
