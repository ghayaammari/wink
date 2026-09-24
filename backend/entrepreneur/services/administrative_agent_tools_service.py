"""Tools de l'administrative_agent (agent reglementaire, EPIC-01,

agents/administrative_agent/) qui ont besoin d'une Session DB -- meme
separation actee que compliance_agent_tools_service.py : agents/ ne touche
jamais la DB directement, ces fonctions sont de simples fermetures sur
(db, user, project_id).

Aucune de ces fonctions n'ecrit en base ni n'appelle une API externe :
lecture seule. Les verifications SIREN/nom restent des services
deterministes independants (name_availability_service.py,
legal_verification_service.py) declenches par un bouton dedie, jamais par
cet agent -- il ne fait que LIRE leurs resultats deja persistes (voir
lire_verifications_administratives_existantes).
"""
import logging
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from agents.ingestion.embedding_service import embed_texts
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.services.name_availability_service import list_name_availability_checks
from backend.entrepreneur.services.project_service import get_owned_project
from backend.entrepreneur.services.roadmap_service import list_roadmap
from backend.shared.knowledge_base.services.content_embeddings_service import search_similar_chunks
from backend.shared.models.user import User

# Meme raisonnement que compliance_agent_tools_service.py (CORRECTIF du
# 22/09/2026) : borner le nombre de chunks et leur taille pour rester sous
# la limite Groq de 8000 TPM/organisation. Corpus administratif = guides
# prose (chunk_texte_guide), en general plus courts que les referentiels
# techniques type SecNumCloud -- valeurs alignees sur compliance_agent par
# prudence plutot que sur une mesure reelle pas encore faite pour ce corpus.
logger = logging.getLogger(__name__)

_TOP_K_CHUNKS = 5
_MAX_CHARS_CHUNK_RETOURNE = 700


def _tronquer_chunk(texte: str, max_chars: int = _MAX_CHARS_CHUNK_RETOURNE) -> str:
    if len(texte) <= max_chars:
        return texte
    return texte[:max_chars] + " [...]"


def _build_rechercher_corpus_administratif(
    db: Session, seen_source_ids: list[str], seen_chunks: list[dict] | None = None
) -> Callable[[str, str], list[dict]]:
    def rechercher_corpus_administratif(domaine: str, requete: str) -> list[dict]:
        """Recherche par similarite semantique dans le corpus administratif

        deja ingere (Bpifrance, Guichet unique/INPI, economie.gouv.fr,
        Legifrance). `domaine` restreint la recherche -- valeurs valides :
        'pacte_fondateurs', 'pre_depot', 'statuts', 'tarifs',
        'annonce_legale', 'forme_juridique', 'statuts_societe', 'roadmap'.
        Jamais une recherche tous domaines confondus. Renvoie une liste de
        chunks {source_id, texte}, ou une liste vide si rien de pertinent
        n'est trouve (dans ce cas, ne pas inventer une regle administrative).
        """
        logger.info("administrative_agent -- tool rechercher_corpus_administratif(domaine=%r, requete=%r)", domaine, requete)
        embedding = embed_texts([requete])[0]
        chunks = search_similar_chunks(db, domaine=domaine, query_embedding=embedding, top_k=_TOP_K_CHUNKS)
        seen_source_ids.extend(chunk.source_id for chunk in chunks)
        resultat = [
            {"source_id": chunk.source_id, "texte": _tronquer_chunk(chunk.chunk_texte)} for chunk in chunks
        ]
        if seen_chunks is not None:
            seen_chunks.extend(resultat)
        return resultat

    return rechercher_corpus_administratif


def _build_lire_profil_projet(db: Session, user: User, project_id: UUID) -> Callable[[], dict]:
    def lire_profil_projet() -> dict:
        """Renvoie le contexte business ET legal deja connu du projet :

        stage, description, secteur declare, PLUS l'identite legale deja
        saisie (forme juridique, denomination, SIREN/SIRET, objet social,
        duree de la societe, date de signature des statuts) si elle existe
        deja -- un projet tres en amont n'a souvent aucun de ces champs
        legaux remplis, ils reviennent alors a None. A appeler pour savoir
        ou en est administrativement l'entrepreneur avant de repondre.
        """
        logger.info("administrative_agent -- tool lire_profil_projet()")
        project = get_owned_project(db, user, project_id)
        legal_profile = (
            db.query(ProjectLegalProfile).filter(ProjectLegalProfile.project_id == project.id).first()
        )

        contexte: dict = {
            "secteur_declare": project.sector,
            "stage": project.stage,
            "description": project.description,
        }

        if legal_profile is None:
            contexte["profil_legal"] = None
            return contexte

        contexte["profil_legal"] = {
            "forme_juridique": legal_profile.legal_form,
            "denomination": legal_profile.legal_name,
            "siren": legal_profile.siren,
            "siret": legal_profile.siret,
            "objet_social": legal_profile.objet_social,
            "duree_societe": legal_profile.duree_societe,
            "date_signature_statuts": (
                legal_profile.date_signature_statuts.isoformat()
                if legal_profile.date_signature_statuts
                else None
            ),
        }
        return contexte

    return lire_profil_projet


def _build_lire_progression_roadmap(db: Session, user: User, project_id: UUID) -> Callable[[], list[dict]]:
    def lire_progression_roadmap() -> list[dict]:
        """Renvoie l'avancement du projet sur les 24 etapes de la roadmap de

        creation (`startup_roadmap_items`) : identifiant, groupe, titre et
        statut ('verrouille' = dependances pas encore satisfaites,
        'a_faire', 'en_cours', 'termine', 'non_necessaire'). A utiliser pour
        savoir quelle est la prochaine etape pertinente pour l'entrepreneur,
        jamais pour repondre a une question de conformite RGPD/AI Act (hors
        perimetre de cet agent).
        """
        logger.info("administrative_agent -- tool lire_progression_roadmap()")
        items = list_roadmap(db, user, project_id)
        return [
            {
                "node_id": item.node_id,
                "groupe": item.groupe,
                "titre": item.node_snapshot.get("titre"),
                "statut": item.statut,
            }
            for item in items
        ]

    return lire_progression_roadmap


def _build_lire_verifications_administratives_existantes(
    db: Session, user: User, project_id: UUID
) -> Callable[[], dict]:
    def lire_verifications_administratives_existantes() -> dict:
        """Renvoie les resultats DEJA persistes des verifications

        administratives : historique des tests de disponibilite de nom
        (denomination + marque, un projet peut en avoir teste plusieurs),
        et les 3 statuts de verification SIREN/Kbis du profil legal
        (denomination_verification_status, immatriculation_verification_status,
        kbis_verification_status -- 'non_verifie'/'verifie'/'incoherent').

        Ne declenche AUCUNE nouvelle verification (pas d'appel API externe
        depuis cet outil) : ces actions restent des boutons dedies cote
        frontend (voir name_availability_service.py, legal_verification_
        service.py). Si l'entrepreneur demande a verifier un nom ou son
        SIREN, redirige-le vers ces actions plutot que d'inventer un
        resultat.
        """
        logger.info("administrative_agent -- tool lire_verifications_administratives_existantes()")
        checks = list_name_availability_checks(db, user, project_id)
        legal_profile = (
            db.query(ProjectLegalProfile)
            .filter(ProjectLegalProfile.project_id == project_id)
            .first()
        )

        return {
            "tests_disponibilite_nom": [
                {
                    "nom_teste": c.nom_teste,
                    "statut_denomination": c.statut_denomination,
                    "statut_marque": c.statut_marque,
                }
                for c in checks
            ],
            "verification_siren_kbis": (
                {
                    "denomination_verification_status": legal_profile.denomination_verification_status,
                    "immatriculation_verification_status": legal_profile.immatriculation_verification_status,
                    "kbis_verification_status": legal_profile.kbis_verification_status,
                }
                if legal_profile is not None
                else None
            ),
        }

    return lire_verifications_administratives_existantes


def build_administrative_agent_tools(
    db: Session,
    user: User,
    project_id: UUID,
    seen_source_ids: list[str],
    seen_chunks: list[dict] | None = None,
) -> list[Callable]:
    """Construit les 4 tools de l'administrative_agent, fermes sur (db, user,

    project_id) pour ce run precis -- voir agents/administrative_agent/
    administrative_agent_service.py pour la definition de l'agent lui-meme.
    Meme convention que build_compliance_agent_tools : `seen_source_ids`
    rempli pendant le run, `seen_chunks` optionnel pour la verification
    d'ancrage du copilot.
    """
    return [
        _build_rechercher_corpus_administratif(db, seen_source_ids, seen_chunks),
        _build_lire_profil_projet(db, user, project_id),
        _build_lire_progression_roadmap(db, user, project_id),
        _build_lire_verifications_administratives_existantes(db, user, project_id),
    ]
