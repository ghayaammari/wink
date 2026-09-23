"""Script ponctuel — a supprimer une fois consulte. Affiche l'etat de la
collecte RGPD a 2 niveaux :
1. Les articles bruts dans `legal_texts` (avant chunking/embedding).
2. Les chunks reellement embeddes dans `content_embeddings` (apres
   validation humaine + chunk_and_embed_legal_texts.py).

Usage (depuis wink/, venv active) :
  python _voir_chunks_rgpd.py
"""
from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings
from backend.shared.knowledge_base.models.legal_texts import LegalText

db = SessionLocal()
try:
    print("=" * 70)
    print("1. Articles bruts dans legal_texts (domaine_reglementaire='rgpd')")
    print("=" * 70)
    articles = (
        db.query(LegalText)
        .filter(LegalText.domaine_reglementaire == "rgpd")
        .order_by(LegalText.type_source, LegalText.article_numero)
        .all()
    )
    print(f"Total : {len(articles)} ligne(s)\n")
    for a in articles:
        print(f"[{a.type_source}] article {a.article_numero} — statut_contenu={a.statut_contenu}")
        print(f"  code_source : {a.code_source}")
        print(f"  sous_theme : {a.sous_theme}")
        print(f"  texte_brut (200 premiers caracteres) : {a.texte_brut[:200]}...")
        print()

    print("=" * 70)
    print("2. Chunks embeddes dans content_embeddings (domaine='rgpd')")
    print("=" * 70)
    chunks = (
        db.query(ContentEmbeddings)
        .filter(ContentEmbeddings.domaine == "rgpd")
        .order_by(ContentEmbeddings.source_type, ContentEmbeddings.source_id, ContentEmbeddings.chunk_index)
        .all()
    )
    print(f"Total : {len(chunks)} chunk(s)\n")
    for c in chunks:
        print(f"[{c.source_type}] source_id={c.source_id} chunk_index={c.chunk_index}")
        print(f"  chunk_texte (200 premiers caracteres) : {c.chunk_texte[:200]}...")
        print()
finally:
    db.close()
