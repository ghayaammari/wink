"""Combien de chunks embeddes existent reellement pour chaque domaine --
prealable indispensable avant d'ecrire des questions golden set pour un
domaine : un domaine autorise par la CheckConstraint (voir migration
h5c7d9e1f3a5) peut tres bien n'avoir aucun contenu scrappe/embedde a ce jour.

Lancement : depuis wink/, venv actif : python list_domaines_disponibles.py
"""
from dotenv import load_dotenv
load_dotenv("backend/.env")

from sqlalchemy import func
from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings

db = SessionLocal()
rows = (
    db.query(ContentEmbeddings.domaine, func.count(ContentEmbeddings.id))
    .group_by(ContentEmbeddings.domaine)
    .order_by(func.count(ContentEmbeddings.id).desc())
    .all()
)
print("=== Chunks embeddes par domaine ===\n")
if not rows:
    print("Aucun chunk trouve en base -- table content_embeddings vide.")
for domaine, nb in rows:
    print(f"  {domaine or '(NULL)':<25} {nb} chunk(s)")
db.close()
