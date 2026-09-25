"""Script ponctuel — a supprimer une fois la reponse obtenue. Verifie si la
collecte RGPD (Legifrance) a deja rempli content_embeddings/legal_texts pour
domaine='rgpd'.

Usage (depuis wink/, venv active) :
  python _check_rgpd_collecte.py
"""
from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.shared.database import SessionLocal
from backend.shared.knowledge_base.models.content_embeddings import ContentEmbeddings
from sqlalchemy import func

db = SessionLocal()
try:
    total = db.query(func.count(ContentEmbeddings.id)).filter(ContentEmbeddings.domaine == "rgpd").scalar()
    print("chunks embeddes domaine=rgpd :", total)

    by_source_type = (
        db.query(ContentEmbeddings.source_type, func.count(ContentEmbeddings.id))
        .filter(ContentEmbeddings.domaine == "rgpd")
        .group_by(ContentEmbeddings.source_type)
        .all()
    )
    print("repartition par source_type :", by_source_type)

    # Essaie aussi legal_texts si le modele existe sous ce nom - a adapter si
    # le nom de fichier/classe differe dans ton arbo.
    try:
        from backend.shared.knowledge_base.models.legal_texts import LegalText

        nb_legal_texts = (
            db.query(func.count(LegalText.id))
            .filter(LegalText.domaine_reglementaire == "rgpd")
            .scalar()
        )
        print("lignes legal_texts domaine_reglementaire=rgpd :", nb_legal_texts)

        lignes = (
            db.query(LegalText.code_source, LegalText.type_source, LegalText.article_numero)
            .filter(LegalText.domaine_reglementaire == "rgpd")
            .all()
        )
        print("lignes (code_source, type_source, article_numero) :")
        for l in lignes:
            print("  ", l)
    except Exception as exc:
        print("(verification legal_texts sautee :", exc, ")")
finally:
    db.close()
