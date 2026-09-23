"""Persistance des embeddings dans `content_embeddings` — pas de logique IA ici,

uniquement de l'upsert. Le calcul du vecteur lui-même vient de
`agents/ingestion/embedding_service.py` — même séparation que
`backend/entrepreneur/services/document_service.py` (DB) vs
`agents/shared/document_processing/` (IA), voir DECISIONS.md.

Ce module ne commit jamais la session : à l'appelant de décider quand committer
(ex: `seed_roadmap_nodes.py` commit une seule fois après avoir upserté tous les
nœuds, transaction atomique — voir docstring du script).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings


def get_embedded_chunks(db: Session, *, source_type: str, source_id: str) -> list[ContentEmbeddings]:
    """Lecture seule : chunks deja en base pour cette source, dans l'ordre
    (chunk_index). Utilisee pour sauter un re-embedding (appel API cher) quand
    rien n'a change depuis le dernier passage — voir
    `chunk_and_embed_legal_texts.py`. Comparer le texte des chunks (pas juste
    verifier qu'une ligne existe) est indispensable : une source revalidee
    apres une correction de contenu retombe dans la liste a traiter, il faut
    detecter que le texte a change pour ne pas la sauter a tort."""
    return (
        db.query(ContentEmbeddings)
        .filter(
            ContentEmbeddings.source_type == source_type,
            ContentEmbeddings.source_id == source_id,
        )
        .order_by(ContentEmbeddings.chunk_index)
        .all()
    )


def upsert_embedding(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    chunk_index: int,
    chunk_texte: str,
    chunk_method: str,
    embedding: list[float],
    modele_utilise: str,
    champ_source: str,
    domaine: str,
    position_reference: str | None = None,
) -> ContentEmbeddings:
    """Insère ou remplace la ligne identifiée par (source_type, source_id, chunk_index) —

    voir UniqueConstraint uq_content_embeddings_source_chunk sur le modèle. Relancer
    un seed/ré-embedding après une correction de texte source ne crée jamais de doublon.
    """
    existing = (
        db.query(ContentEmbeddings)
        .filter(
            ContentEmbeddings.source_type == source_type,
            ContentEmbeddings.source_id == source_id,
            ContentEmbeddings.chunk_index == chunk_index,
        )
        .first()
    )
    if existing is not None:
        existing.chunk_texte = chunk_texte
        existing.chunk_method = chunk_method
        existing.embedding = embedding
        existing.modele_utilise = modele_utilise
        existing.champ_source = champ_source
        existing.domaine = domaine
        existing.position_reference = position_reference
        db.flush()
        return existing

    row = ContentEmbeddings(
        source_type=source_type,
        source_id=source_id,
        chunk_index=chunk_index,
        chunk_texte=chunk_texte,
        chunk_method=chunk_method,
        embedding=embedding,
        modele_utilise=modele_utilise,
        champ_source=champ_source,
        domaine=domaine,
        position_reference=position_reference,
    )
    db.add(row)
    db.flush()
    return row


def resolve_legal_text_id(db: Session, *, source_id: str) -> UUID | None:
    """Resout un `source_id` vu par le compliance_agent (via son tool

    rechercher_corpus_reglementaire, deja verifie comme reellement vu
    pendant le run par l'appelant -- voir seen_source_ids dans
    compliance_agent_tools_service.py) en `legal_text_id` reel, uniquement
    s'il correspond a une ligne source_type='legal_texts'. Protege les
    tables d'obligations (AI Act, RGPD) contre un identifiant qui pointerait
    en fait vers un autre source_type (roadmap_node, contract_clauses_
    library...) -- retourne None si le source_id est absent ou d'un autre
    source_type, jamais une erreur bloquante (meme convention que
    l'ancienne resolution par index hors limites qu'elle remplace).
    """
    row = (
        db.query(ContentEmbeddings.source_id)
        .filter(ContentEmbeddings.source_id == source_id, ContentEmbeddings.source_type == "legal_texts")
        .first()
    )
    return UUID(source_id) if row is not None else None


def search_similar_chunks(
    db: Session, *, domaine: str, query_embedding: list[float], top_k: int = 8
) -> list[ContentEmbeddings]:
    """Recherche par similarite cosinus, restreinte a un `domaine` (voir

    colonne du modele) — jamais une recherche tous domaines confondus : un
    diagnostic RGPD n'a rien a faire d'un chunk 'assurance_sectorielle'.
    Premiere utilisatrice reelle : agents/compliance_agent/rgpd_service.py,
    via l'orchestration du service compliance (cette fonction reste ici,
    DB uniquement — l'agent ne recoit que les ContentEmbeddings deja
    recuperes, jamais une Session, voir separation agents/ vs backend/).
    """
    return (
        db.query(ContentEmbeddings)
        .filter(ContentEmbeddings.domaine == domaine)
        .order_by(ContentEmbeddings.embedding.cosine_distance(query_embedding))
        .limit(top_k)
        .all()
    )
