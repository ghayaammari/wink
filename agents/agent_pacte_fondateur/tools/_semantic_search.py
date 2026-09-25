"""Recherche semantique dans `content_embeddings`, filtree par domaine --
premiere recherche en temps reel du repo (jusqu'ici, `content_embeddings`
n'etait qu'ecrit en batch par les scripts de seed/collecte, jamais interroge
par similarite a la volee).

DETTE TECHNIQUE ASSUMEE, deja anticipee et documentee dans
`agents/ingestion/embedding_service.py` (section "Dette technique assumee") :
`embed_texts()` charge le modele BGE-M3 (~2 Go) dans le process appelant.
Cette fonction l'appelle directement depuis un endpoint HTTP temps reel (le
copilot) -- exactement le cas que embedding_service.py disait "tenir tant
qu'aucun endpoint temps reel n'en a besoin". Ce n'est plus le cas a partir
d'ici. Pas resolu dans ce travail (deploiement d'un service d'embedding
separe = chantier d'infra a part, hors perimetre de l'agent copilot) --
signale explicitement, pas silencieusement reconduit.

ISOLATION VOLONTAIRE : cette fonction vit dans agent_pacte_fondateur/ plutot
que dans `backend/shared/knowledge_base/services/content_embeddings_service.py`
(qui serait l'emplacement naturel, partage par tout futur agent) -- pour ne
pas toucher un fichier partage que la binome modifie peut-etre en parallele
pour son propre copilot (Groupe 3). Duplication probable le jour de la
fusion -- assumee, voir docstring de pacte_fondateurs_conversation.py.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.ingestion.embedding_service import embed_texts
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings
from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary
from backend.shared.knowledge_base.models.legal_texts import LegalText

DOMAINE_PACTE_FONDATEURS = "pacte_fondateurs"


def search_similar_chunks(db: Session, *, query_texte: str, k: int = 5) -> list[ContentEmbeddings]:
    """Retourne les `k` chunks les plus proches semantiquement de `query_texte`,
    dans le domaine 'pacte_fondateurs' uniquement -- jamais tous domaines
    confondus, pour ne pas melanger le corpus pacte fondateurs avec celui
    d'un autre service (ex: forme_juridique) dans une reponse du copilot.

    Cas limite : `query_texte` vide -- embed_texts([""]) produirait un vecteur
    sans signification, la recherche renverrait des resultats aleatoires.
    Refuse explicitement plutot que de renvoyer un faux resultat.
    """
    if not query_texte or not query_texte.strip():
        return []

    query_embedding = embed_texts([query_texte])[0]

    stmt = (
        select(ContentEmbeddings)
        .where(ContentEmbeddings.domaine == DOMAINE_PACTE_FONDATEURS)
        .order_by(ContentEmbeddings.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    return list(db.execute(stmt).scalars().all())


def resolve_citation(db: Session, *, source_type: str, source_id: str) -> str | None:
    """Resout un libelle humain (ex: "Code civil, art. 1843-4") depuis
    `source_type`/`source_id`, sans jamais deviner : renvoie None si la ligne
    source n'existe plus. Factorisee de `to_citable_chunks()` (25/09/2026)
    pour etre reutilisee par `obtenir_historique()` cote service -- la table
    `pacte_fondateurs_response_sources` ne persiste que source_type/source_id
    (polymorphe, voir sa docstring), la citation doit donc etre re-resolue a
    chaque lecture de l'historique plutot que stockee (peut changer si
    `legal_texts` est corrige entre-temps -- comportement voulu, pas un bug)."""
    if source_type == "legal_texts":
        legal_text = db.get(LegalText, source_id)
        if legal_text is not None:
            return f"{legal_text.code_source}, {legal_text.article_numero or 'texte entier'}"
    # CORRIGE (26/09/2026) : source_type="contract_clauses_library" n'etait pas
    # resolu -- citation toujours None pour ce cas, alors qu'il est courant
    # (chunks embeddes sur description_clause/texte_clause, voir content_embeddings.py).
    # Cote frontend le vide s'affichait "(source non resolue)", et le LLM,
    # prive d'un libelle humain exploitable, comblait le vide en improvisant
    # des references non retournees par la tool (jurisprudence, guides
    # externes -- jamais presentes dans ce corpus). Resoudre ici retire la
    # tentation : le LLM recoit desormais toujours un libelle citable pour
    # toute source reellement retrouvee.
    if source_type == "contract_clauses_library":
        clause = db.get(ContractClauseLibrary, source_id)
        if clause is not None:
            return f'"{clause.titre_clause}" (modele {clause.source_modele})'
    return None


def to_citable_chunks(db: Session, chunks: list[ContentEmbeddings]) -> list[dict]:
    """Transforme des lignes `content_embeddings` en payload citable par le
    LLM : {chunk_texte, source_type, source_id, citation}. `citation` est un
    libelle humain resolu via `resolve_citation()` -- seul type de source
    existant a ce jour est 'legal_texts' (voir content_embeddings.py :
    "roadmap_node", "legal_texts", "contract_clauses_library" a terme).
    """
    resultats = []
    for chunk in chunks:
        citation = resolve_citation(db, source_type=chunk.source_type, source_id=chunk.source_id)
        resultats.append({
            "chunk_texte": chunk.chunk_texte,
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "citation": citation,
        })
    return resultats
