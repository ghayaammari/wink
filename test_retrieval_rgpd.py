"""Test retrieval seul -- domaine 'rgpd', 3 questions reelles.
Lancement : depuis wink/, venv actif : python test_retrieval_rgpd.py
"""
from dotenv import load_dotenv
load_dotenv("backend/.env")

from agents.ingestion.embedding_service import embed_texts
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.services.content_embeddings_service import search_similar_chunks

QUESTIONS = [
    "Quelles sont les obligations en cas de profilage automatise des utilisateurs ?",
    "Faut-il un contrat de sous-traitance pour partager des donnees avec un prestataire ?",
    "Quelles regles s'appliquent au transfert de donnees hors Union europeenne ?",
]

db = SessionLocal()
for question in QUESTIONS:
    print(f"\n=== Question : {question} ===")
    embedding = embed_texts([question])[0]
    chunks = search_similar_chunks(db, domaine="rgpd", query_embedding=embedding, top_k=3)
    if not chunks:
        print("  Aucun chunk trouve.")
    for chunk in chunks:
        print(f"  - [{chunk.source_id}] {chunk.chunk_texte[:150]}...")
db.close()
