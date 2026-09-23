"""Logique métier de `aipd_analyses` — service 3.3.4 (AIPD), déclenché depuis
la carte RGPD (3.3.1). `create_analysis` est le point d'entrée bas niveau qui
persiste un contenu déjà généré ; `generate_analysis` est le point d'entrée
réel côté route : il orchestre la recherche vectorielle + l'appel au
compliance_agent (agents/ ne touche jamais la DB, voir séparation agents/ vs
backend/<acteur>/services/) puis appelle create_analysis. Même découpage que
rgpd_diagnostic_service.run_diagnostic() pour le service 3.3.1.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.ingestion.embedding_service import embed_texts
from agents.compliance_agent.rgpd_service import SourceChunk, generate_aipd_document, generate_aipd_verification
from backend.entrepreneur.models.aipd_analysis import AipdAnalysis
from backend.entrepreneur.models.project_rgpd_obligation import ProjectRgpdObligation
from backend.entrepreneur.services.compliance_data_profile_service import build_profil_context, get_or_create_profile
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.knowledge_base.services.content_embeddings_service import search_similar_chunks
from backend.shared.models.user import User

_TOP_K_CHUNKS_PAR_SECTION = 4

# Ajoute le 18/09/2026 (suite a une AIPD generee citant le "Bouclier de
# protection des donnees", mecanisme invalide depuis l'arret Schrems II de
# la CJUE en 2020 - le LLM peut hallucine un mecanisme juridique precis et
# perime malgre la consigne du prompt). Ce disclaimer est ajoute ici, en
# code, plutot que demande au LLM dans le prompt : une regle de prompt peut
# ne pas etre suivie, un texte fixe concatene apres coup est garanti present
# a chaque generation, quoi que produise le LLM.
_DISCLAIMER_AIPD = (
    "\n\n---\n"
    "Ce document est un brouillon genere automatiquement a partir des "
    "reponses du diagnostic RGPD. Il doit etre relu et valide par un "
    "professionnel (DPO ou juriste) avant toute utilisation, en particulier "
    "les mecanismes juridiques cites (transferts hors UE, contrats avec des "
    "tiers), qui doivent etre verifies comme etant toujours en vigueur."
)

# RAG agentique (ajoute le 18/09/2026, remplace un retrieval unique +
# generation en un seul appel LLM) : une requete de recherche vectorielle
# dediee par section, plutot qu'une seule requete generique pour tout le
# document — chaque section a un besoin de sources different (finalites vs
# risques vs mesures), un retrieval unique diluait la pertinence par
# section. Cout : recherche vectorielle = gratuite (pas de tokens Groq).
# Cote generation, un seul appel LLM (generate_aipd_document) redige les 4
# sections d'un coup a partir des chunks groupes par section, puis
# generate_aipd_verification en fait un 2e — 2 appels Groq au total. Une
# premiere version faisait 1 appel LLM PAR section (5 appels au total) ;
# repassee a un seul appel de generation le 18/09/2026 (quota Groq TPD
# limite, voir discussion) car le retrieval cible par section est ce qui
# comptait le plus pour la qualite, pas le fait d'avoir un appel LLM dedie
# par section.
SECTIONS_AIPD = [
    {
        "cle": "finalites",
        "titre": "1. Description du traitement et de ses finalites",
        "consignes": "Decris le traitement de donnees et ses finalites, a partir du profil et du secteur/description du projet.",
        "requete": "finalites et description d'un traitement de donnees personnelles, secteur d'activite",
    },
    {
        "cle": "necessite_proportionnalite",
        "titre": "2. Necessite et proportionnalite du traitement au regard des finalites",
        "consignes": "Explique en quoi le traitement est necessaire et proportionne aux finalites decrites en section 1, sans reprendre ces finalites en detail.",
        "requete": "principe de necessite et de proportionnalite du traitement de donnees personnelles au regard de la finalite",
    },
    {
        "cle": "risques",
        "titre": "3. Risques pour les droits et libertes des personnes concernees",
        "consignes": "Identifie les risques pour les personnes concernees a partir des elements du profil (donnees sensibles, mineurs, profilage, partage avec des tiers, transfert hors UE).",
        "requete": "risques pour les droits et libertes des personnes concernees : donnees sensibles, mineurs, profilage, transfert de donnees hors UE, partage avec des tiers",
    },
    {
        "cle": "mesures",
        "titre": "4. Mesures envisagees pour traiter ces risques (techniques et organisationnelles)",
        "consignes": "Propose des mesures techniques et organisationnelles pour traiter les risques identifies en section 3, sans repeter ces risques en detail.",
        "requete": "mesures techniques et organisationnelles de securite et de protection des donnees personnelles",
    },
]


def list_analyses(db: Session, user: User, project_id: UUID) -> list[AipdAnalysis]:
    project = get_owned_project(db, user, project_id)
    return (
        db.query(AipdAnalysis)
        .filter(AipdAnalysis.project_id == project.id)
        .order_by(AipdAnalysis.generated_at.desc())
        .all()
    )


def create_analysis(
    db: Session, user: User, project_id: UUID, contenu: str, project_rgpd_obligation_id: UUID | None = None
) -> AipdAnalysis:
    project = get_owned_project(db, user, project_id)
    analysis = AipdAnalysis(
        project_id=project.id,
        project_rgpd_obligation_id=project_rgpd_obligation_id,
        contenu=contenu,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def generate_analysis(db: Session, user: User, project_id: UUID) -> AipdAnalysis:
    """Point d'entrée réel du service 3.3.4, appelé par la route "Faire mon

    AIPD" — pipeline RAG agentique en 2 étapes (voir SECTIONS_AIPD) :
    1. Pour chaque section, une recherche vectorielle ciblée récupère les
       chunks les plus pertinents à CETTE section (gratuit, pas de tokens
       Groq), puis generate_aipd_document rédige les 4 sections en un seul
       appel LLM, chacune à partir de ses propres chunks.
    2. Le document généré passe par generate_aipd_verification, qui relit
       chaque affirmation contre l'ensemble des chunks utilisés et reformule
       ce qui n'est pas justifié.
    2 appels Groq au total (voir commentaire sur SECTIONS_AIPD ci-dessus).
    Lie automatiquement l'analyse à l'obligation `lie_a_aipd=true` du projet
    si elle existe (nullable sinon — voir docstring du modèle AipdAnalysis).
    """
    project = get_owned_project(db, user, project_id)
    profile = get_or_create_profile(db, user, project_id)
    profil_context = build_profil_context(profile, project)

    sections_pour_agent: list[dict] = []
    tous_les_chunks: list[SourceChunk] = []
    for section in SECTIONS_AIPD:
        query_embedding = embed_texts([section["requete"]])[0]
        embedded_chunks = search_similar_chunks(
            db, domaine="rgpd", query_embedding=query_embedding, top_k=_TOP_K_CHUNKS_PAR_SECTION
        )
        chunks_section = [SourceChunk(source_id=c.source_id, texte=c.chunk_texte) for c in embedded_chunks]
        tous_les_chunks.extend(chunks_section)
        sections_pour_agent.append(
            {"titre": section["titre"], "consignes": section["consignes"], "chunks": chunks_section}
        )

    resultat_document = generate_aipd_document(profil_context, sections_pour_agent)
    resultat_verifie = generate_aipd_verification(resultat_document.contenu, tous_les_chunks)

    obligation_aipd = (
        db.query(ProjectRgpdObligation)
        .filter(ProjectRgpdObligation.project_id == project.id, ProjectRgpdObligation.lie_a_aipd.is_(True))
        .first()
    )
    project_rgpd_obligation_id = obligation_aipd.id if obligation_aipd is not None else None

    contenu_avec_disclaimer = resultat_verifie.contenu + _DISCLAIMER_AIPD
    return create_analysis(
        db, user, project_id, contenu_avec_disclaimer, project_rgpd_obligation_id=project_rgpd_obligation_id
    )
