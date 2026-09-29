"""Tools du compliance_agent (agent conformite, EPIC-03, agents/

compliance_agent/) qui ont besoin d'une Session DB -- construits ici et non
dans agents/, parce que la separation actee du projet reste stricte :
agents/ ne touche jamais la DB directement (voir docstring de
search_similar_chunks). Ces fonctions sont de simples fermetures sur
(db, user, project_id) : le module agents/ reste generique et ne connait ni
SQLAlchemy ni FastAPI, seulement des fonctions Python passees en parametre a
l'agent (voir agents/compliance_agent/healthtech_gap_analysis_service.py).

Aucune de ces fonctions n'ecrit en base : lecture seule. La persistance d'un
resultat reste toujours du ressort du service appelant (upsert_result,
etc.), jamais de l'agent -- voir conversation produit sur les limites
volontaires de cet agent (pas de web search, pas d'ecriture en base, pas de
cochage automatique d'une obligation comme accomplie).
"""
import logging
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from agents.ingestion.embedding_service import embed_texts
from agents.shared.reranking.reranking_service import rerank_indices
from backend.entrepreneur.services.ai_act_data_profile_service import (
    get_or_create_profile as get_or_create_ai_act_profile,
)
from backend.entrepreneur.services.compliance_data_profile_service import (
    get_or_create_profile as get_or_create_rgpd_profile,
)
from backend.entrepreneur.services.fintech_data_profile_service import (
    get_or_create_profile as get_or_create_fintech_profile,
)
from backend.entrepreneur.services.healthtech_data_profile_service import (
    get_or_create_profile as get_or_create_healthtech_profile,
)
from backend.entrepreneur.services.project_ai_act_classification_service import (
    get_or_create_classification as get_or_create_ai_act_classification,
)
from backend.entrepreneur.services.project_fintech_classification_service import (
    get_or_create_classification as get_or_create_fintech_classification,
)
from backend.entrepreneur.services.project_fintech_gap_analysis_service import (
    get_result as get_fintech_gap_analysis_result,
)
from backend.entrepreneur.services.project_healthtech_classification_service import (
    get_or_create_classification as get_or_create_healthtech_classification,
)
from backend.entrepreneur.services.project_ai_act_obligation_service import (
    get_score as get_ai_act_score,
    list_obligations as list_ai_act_obligations,
)
from backend.entrepreneur.services.project_fintech_gap_analysis_service import get_score as get_fintech_score
from backend.entrepreneur.services.project_healthtech_gap_analysis_service import (
    get_chapter_status_list,
    get_score as get_healthtech_score,
)
from backend.entrepreneur.services.project_rgpd_obligation_service import get_score as get_rgpd_score, list_obligations
from backend.entrepreneur.services.project_sector_detection_service import get_or_create_detection
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.knowledge_base.services.content_embeddings_service import search_similar_chunks
from backend.shared.models.user import User

# CORRECTIF du 22/09/2026 -- 8 avant : sur le premier run reel du sous-agent
# SecNumCloud (chunks de referentiel PDF technique, plus denses que les
# articles RGPD courts), 8 chunks + system prompt depassaient la limite Groq
# de tokens/minute (8000 TPM, tier on_demand de l'org), erreur 413 "Request
# too large" -- pas une 429 (la rotation de cles ne peut rien y faire, une
# requete trop grosse depasse la limite avec n'importe quelle cle). Baisse a
# 5 : impact global (6 sous-agents + copilot partagent ce meme tool), mais le
# risque allait au-dela de SecNumCloud des qu'un domaine a des chunks plus
# gros que la moyenne RGPD -- pas une rustine locale a un seul agent.
# CORRECTIF du 22/09/2026 (v3) -- 5 avant : meme apres la troncature des
# chunks (v2 ci-dessous) et des organisations Groq separees, un run complet
# de compliance_agent_secnumcloud continuait a saturer 8000 TPM en fin de
# run ("Used 7400, Requested 5516") -- chaque chunk, meme tronque, reste dans
# l'historique envoye a CHAQUE etape suivante, donc son poids se multiplie
# par le nombre d'etapes restantes. Baisse a 3 : reduit ce cout cumule
# directement a la source (moins de chunks a transporter dans l'historique),
# complementaire a la troncature plutot qu'un remplacement. Meme compromis
# assume qu'en v2 : un peu moins de contexte par recherche, pour tenir dans
# le tier gratuit.
logger = logging.getLogger(__name__)

_TOP_K_CHUNKS = 3

# CORRECTIF du 22/09/2026 (v2) -- meme apres la baisse ci-dessus (alors a 5),
# un run complet de compliance_agent_secnumcloud (2 recherches x 5 chunks,
# chunks PDF jusqu'a 1500 caracteres chacun) consommait a lui seul ~8800
# tokens Groq avant meme la fin du raisonnement (constate : "Used 3998,
# Requested 4885" sur une organisation pourtant fraiche) -- chaque chunk
# retourne par l'outil reste dans l'historique envoye a CHAQUE etape
# suivante du ReAct, donc son poids se multiplie par le nombre d'etapes
# restantes, pas juste compte une fois. Ni la rotation de cles (key_pool.py)
# ni des comptes Groq separes ne peuvent corriger ca : le run entier
# redemarre de zero sur chaque cle et retombe sur le meme mur, puisque le
# probleme est la taille du run lui-meme, pas un quota deja occupe par autre
# chose. Tronque chaque chunk a _MAX_CHARS_CHUNK_RETOURNE avant de le
# renvoyer au modele -- dette technique assumee (moins de detail par chunk,
# un long chunk referentiel peut perdre sa fin) pour tenir dans le tier Groq
# gratuit (8000 TPM/org) ; a revisiter si le projet passe un jour sur un
# tier payant.
#
# CORRECTIF du 22/09/2026 (v4) -- 1000 avant : encore trop juste apres la v3
# (constate : "Used 4775, Requested 4060", depassement de ~835 tokens, contre
# ~4875 puis ~4675 lors des tentatives precedentes -- amelioration reelle
# mais a prendre avec prudence, chaque tentative teste une cle differente du
# pool avec son propre historique recent, la comparaison brute d'une
# tentative a l'autre n'isole pas parfaitement l'effet de ce correctif seul).
#
# CORRECTIF du 22/09/2026 (v6) -- 700 avant : apres le profil allege pour
# SecNumCloud (v5, _build_lire_profil_projet), l'ecart continue de se
# resserrer ("Used 4967, Requested 3319", depassement de ~286 tokens
# seulement, contre ~835 avant v5) -- tres proche du seuil. Derniere baisse
# pour passer sous la limite plutot que compter sur le hasard du
# renouvellement de fenetre TPM entre deux clics.
_MAX_CHARS_CHUNK_RETOURNE = 500


def _tronquer_chunk(texte: str, max_chars: int = _MAX_CHARS_CHUNK_RETOURNE) -> str:
    """Coupe un chunk trop long avant de le renvoyer au modele -- voir le

    CORRECTIF du 22/09/2026 (v2) ci-dessus. Ne coupe jamais un chunk deja
    assez court (cas normal pour la plupart des sources RGPD/AI Act) ; ajoute
    un marqueur explicite "[...]" pour que l'agent sache que le chunk est
    incomplet plutot que de croire a tort qu'il a tout le texte.
    """
    if len(texte) <= max_chars:
        return texte
    return texte[:max_chars] + " [...]"


def _build_rechercher_corpus_reglementaire(
    db: Session, seen_source_ids: list[str], seen_chunks: list[dict] | None = None
) -> Callable[[str, str], list[dict]]:
    """Ferme sur `db` uniquement : recherche dans un corpus partage, jamais

    scopee a un projet (voir search_similar_chunks). `seen_source_ids` est
    rempli au fil des appels -- sert ensuite a l'appelant (backend) pour
    verifier que chaque source_id renvoye par l'agent correspond bien a un
    chunk reellement vu pendant ce run, jamais un identifiant invente.

    `seen_chunks` (optionnel, None par defaut pour ne rien changer aux 5
    sous-agents de diagnostic qui ne le passent pas) rejoue le meme principe
    mais garde le texte complet des chunks, pas seulement leur id -- utilise
    par le copilot pour la verification d'ancrage a posteriori (voir
    grounding_verification_service.py), qui a besoin du contenu, pas
    seulement de savoir qu'un id a ete vu.
    """

    def rechercher_corpus_reglementaire(domaine: str, requete: str) -> list[dict]:
        """Recherche par similarite semantique dans le corpus legal interne

        deja ingere (CNIL, Legifrance, MDR, Code monetaire et financier...).
        `domaine` restreint la recherche (ex: 'secteur_healthtech',
        'secteur_fintech', 'rgpd', 'ai_act') -- jamais une recherche tous
        domaines confondus. Renvoie une liste de chunks {source_id, texte},
        ou une liste vide si rien de pertinent n'est trouve (dans ce cas, ne
        pas inventer d'obligation).
        """
        logger.info("compliance_agent -- tool rechercher_corpus_reglementaire(domaine=%r, requete=%r)", domaine, requete)
        embedding = embed_texts([requete])[0]
        chunks = search_similar_chunks(db, domaine=domaine, query_embedding=embedding, top_k=_TOP_K_CHUNKS)

        # Reranking (voir claude/Wink_rag_retrieval_eval_baseline.md) : reordonne
        # les memes _TOP_K_CHUNKS candidats deja recuperes par similarite cosinus,
        # ne change ni leur nombre ni le recall -- corrige seulement le rang du
        # bon chunk sur les domaines a articles semantiquement proches.
        if chunks:
            ordre = rerank_indices(requete, [chunk.chunk_texte for chunk in chunks])
            chunks = [chunks[i] for i in ordre]

        seen_source_ids.extend(chunk.source_id for chunk in chunks)
        resultat = [
            {"source_id": chunk.source_id, "texte": _tronquer_chunk(chunk.chunk_texte)} for chunk in chunks
        ]
        if seen_chunks is not None:
            seen_chunks.extend(resultat)
        return resultat

    return rechercher_corpus_reglementaire


def _build_lire_profil_projet(
    db: Session, user: User, project_id: UUID, inclure_questionnaires_generaux: bool = True
) -> Callable[[], dict]:
    """`inclure_questionnaires_generaux` (True par defaut, ne change rien aux

    5 sous-agents de diagnostic existants) : CORRECTIF du 22/09/2026 (v5) --
    compliance_agent_secnumcloud n'a besoin que de "stage" dans ce profil
    (voir prompts.yaml, compliance_agent_secnumcloud.parcours), pourtant
    lire_profil_projet renvoyait systematiquement ~11 champs de questionnaires
    RGPD/AI Act sans rapport avec SecNumCloud -- poids mort qui reste dans
    l'historique pour le reste du run comme n'importe quel autre contenu
    (voir CORRECTIF v2/v3/v4 ci-dessus sur le meme mecanisme). Passe a False
    uniquement pour SecNumCloud (secnumcloud_diagnostic_service.py) ; les
    5 autres sous-agents ne changent pas d'appel, donc gardent True.
    """

    def lire_profil_projet() -> dict:
        """Renvoie le contexte reglementaire ET business deja connu du

        projet : secteur declare (texte libre) et secteur detecte,
        classification (classe de risque MDR ou type d'agrement FinTech) si
        elle existe, reponses aux questionnaires RGPD/AI Act/sectoriel (si
        pertinents pour ce sous-agent, voir inclure_questionnaires_generaux),
        et les champs business pertinents du projet (stage, description,
        technologies, customer_segments, target_users, value_proposition).
        A appeler pour contextualiser une generation -- jamais pour savoir
        si une obligation est deja accomplie dans la realite (voir
        lire_diagnostics_existants pour ca).

        questionnaire_rgpd et questionnaire_ai_act sont inclus par defaut
        (pas conditionnes au secteur detecte) : RGPD et AI Act s'appliquent
        potentiellement a tout projet, contrairement aux questionnaires
        HealthTech/FinTech qui ne concernent que les projets de ce secteur --
        sauf si le sous-agent appelant n'en a explicitement pas besoin (voir
        inclure_questionnaires_generaux).
        """
        logger.info("compliance_agent -- tool lire_profil_projet()")
        project = get_owned_project(db, user, project_id)
        detection = get_or_create_detection(db, user, project_id)

        contexte: dict = {
            "secteur_declare": project.sector,
            "secteur_detecte": detection.secteur_detecte,
            "stage": project.stage,
            "description": project.description,
            "technologies": project.technologies,
            "customer_segments": project.customer_segments,
            "target_users": project.target_users,
            "value_proposition": project.value_proposition,
        }

        if not inclure_questionnaires_generaux:
            return contexte

        rgpd_profile = get_or_create_rgpd_profile(db, user, project_id)
        ai_act_profile = get_or_create_ai_act_profile(db, user, project_id)
        contexte.update({
            "questionnaire_rgpd": {
                "collecte_donnees_sensibles": rgpd_profile.collecte_donnees_sensibles,
                "collecte_donnees_mineurs": rgpd_profile.collecte_donnees_mineurs,
                "profilage": rgpd_profile.profilage,
                "partage_avec_tiers": rgpd_profile.partage_avec_tiers,
                "transfert_hors_ue": rgpd_profile.transfert_hors_ue,
            },
            "questionnaire_ai_act": {
                "utilise_ia": ai_act_profile.utilise_ia,
                "usage_biometrie_ou_identification": ai_act_profile.usage_biometrie_ou_identification,
                "usage_scoring_emploi_credit_ou_education": ai_act_profile.usage_scoring_emploi_credit_ou_education,
                "usage_infrastructure_ou_securite_critique": ai_act_profile.usage_infrastructure_ou_securite_critique,
                "interagit_ou_genere_contenu_pour_utilisateurs": (
                    ai_act_profile.interagit_ou_genere_contenu_pour_utilisateurs
                ),
                "developpe_modele_ia_usage_general": ai_act_profile.developpe_modele_ia_usage_general,
            },
        })

        if detection.secteur_detecte == "healthtech":
            profile = get_or_create_healthtech_profile(db, user, project_id)
            classification = get_or_create_healthtech_classification(db, user, project_id)
            contexte["questionnaire_healthtech"] = {
                "est_dispositif_medical": profile.est_dispositif_medical,
                "fournit_aide_decision_diagnostique_ou_therapeutique": (
                    profile.fournit_aide_decision_diagnostique_ou_therapeutique
                ),
                "risque_deces_ou_deterioration_irreversible": profile.risque_deces_ou_deterioration_irreversible,
                "risque_intervention_chirurgicale_ou_deterioration_grave": (
                    profile.risque_intervention_chirurgicale_ou_deterioration_grave
                ),
            }
            contexte["classe_risque"] = classification.classe_risque
        elif detection.secteur_detecte == "fintech":
            profile = get_or_create_fintech_profile(db, user, project_id)
            classification = get_or_create_fintech_classification(db, user, project_id)
            contexte["questionnaire_fintech"] = {
                "gere_fonds_ou_paiements_clients": profile.gere_fonds_ou_paiements_clients,
                "volume_mensuel_depasse_3_millions": profile.volume_mensuel_depasse_3_millions,
                "propose_transmission_de_fonds": profile.propose_transmission_de_fonds,
                "gere_investissement_ou_actifs": profile.gere_investissement_ou_actifs,
            }
            contexte["type_agrement"] = classification.type_agrement

        return contexte

    return lire_profil_projet


def _build_lire_diagnostics_existants(db: Session, user: User, project_id: UUID) -> Callable[[], dict]:
    def lire_diagnostics_existants() -> dict:
        """Renvoie les resultats deja persistes pour ce projet (obligations

        RGPD, classification AI Act, chapitres de gap-analysis HealthTech/
        FinTech avec leurs obligations et le statut manuel "accompli"), PLUS
        le score de conformite deja calcule pour chaque domaine (champ
        "score", meme calcul que le dashboard -- voir
        compliance_score_service.compute_compliance_score).

        Le champ "score" de chaque domaine est la SEULE source a utiliser
        pour repondre a une question sur un pourcentage de conformite --
        ne jamais recompter les obligations "a la main" a partir de la
        liste brute, l'agent obtiendrait un chiffre different (arrondi,
        erreur de comptage) de celui affiche au dashboard.

        Attention pour HealthTech : le "statut_generation" d'un chapitre
        ("fait" = ce chapitre a ete genere, "debloque"/"verrouille" = pas
        encore) ne dit RIEN sur la conformite -- un chapitre "fait" peut
        tres bien n'avoir aucune obligation accomplie. Utilise uniquement
        "healthtech_gap_analysis.score" pour la conformite HealthTech,
        jamais "statut_generation".
        """
        logger.info("compliance_agent -- tool lire_diagnostics_existants()")
        rgpd_obligations = list_obligations(db, user, project_id)
        ai_act_obligations = list_ai_act_obligations(db, user, project_id)
        ai_act_classification = get_or_create_ai_act_classification(db, user, project_id)
        healthtech_statuses = get_chapter_status_list(db, user, project_id)
        fintech_result = get_fintech_gap_analysis_result(db, user, project_id)

        return {
            "rgpd_obligations": [
                {"nom": o.nom, "description": o.description, "statut": o.statut} for o in rgpd_obligations
            ],
            "rgpd_score": get_rgpd_score(db, user, project_id).model_dump(),
            "ai_act_classification": ai_act_classification.categorie_risque,
            "ai_act_obligations": [
                {"nom": o.nom, "description": o.description, "statut": o.statut} for o in ai_act_obligations
            ],
            "ai_act_score": get_ai_act_score(db, user, project_id).model_dump(),
            "healthtech_gap_analysis": {
                "chapitres": [
                    {
                        "chapitre": s.cle,
                        "statut_generation": s.statut,
                        "obligations": s.resultat.obligations["obligations"] if s.resultat else [],
                    }
                    for s in healthtech_statuses
                ],
                "score": get_healthtech_score(db, user, project_id).model_dump(),
            },
            "fintech_gap_analysis": (
                {
                    "obligations": fintech_result.obligations["obligations"],
                    "justification": fintech_result.justification,
                    "score": get_fintech_score(db, user, project_id).model_dump(),
                }
                if fintech_result
                else None
            ),
        }

    return lire_diagnostics_existants


def build_compliance_agent_tools(
    db: Session,
    user: User,
    project_id: UUID,
    seen_source_ids: list[str],
    seen_chunks: list[dict] | None = None,
    inclure_questionnaires_generaux: bool = True,
) -> list[Callable]:
    """Construit les 3 tools du compliance_agent, fermes sur (db, user,

    project_id) pour ce run precis -- voir agents/compliance_agent/*.py
    pour la definition de l'agent lui-meme (system prompt, schema de
    sortie), qui reste sans acces DB direct. `seen_source_ids` (liste vide
    fournie par l'appelant) est remplie pendant le run par
    rechercher_corpus_reglementaire -- l'appelant s'en sert ensuite pour
    valider les source_id renvoyes par l'agent. `seen_chunks` : voir
    docstring de _build_rechercher_corpus_reglementaire, seul copilot_service.py
    le passe pour l'instant. `inclure_questionnaires_generaux` : voir
    docstring de _build_lire_profil_projet (CORRECTIF v5) -- True par defaut,
    ne change rien aux appelants existants.
    """
    return [
        _build_rechercher_corpus_reglementaire(db, seen_source_ids, seen_chunks),
        _build_lire_profil_projet(db, user, project_id, inclure_questionnaires_generaux),
        _build_lire_diagnostics_existants(db, user, project_id),
    ]
