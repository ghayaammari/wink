"""Connexion Supabase/PostgreSQL et Base déclarative commune à tout le backend.

Toutes les tables (shared, entrepreneur, chercheur, investisseur) héritent de `Base`
définie ici, pour qu'Alembic les détecte toutes depuis un seul metadata.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# os.environ ne lit jamais le fichier .env tout seul — sans cet appel, DATABASE_URL
# resterait absent même avec un .env rempli à côté (ça ne casse rien en prod : la
# vraie variable d'environnement est déjà injectée par la plateforme d'hébergement).
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]  # ex: postgresql+psycopg://user:pwd@host:5432/dbname

# prepare_threshold=None : désactive les prepared statements côté serveur pour
# psycopg. Nécessaire avec le pooler Supabase en mode transaction (port 6543,
# PgBouncer) — ce mode peut faire changer la connexion physique sous-jacente
# entre deux requêtes, ce qui casse les prepared statements (ils n'existent que
# sur UNE connexion physique) et lève `DuplicatePreparedStatement`. Sans objet
# sur une connexion directe (port 5432), donc sans risque de régression si le
# projet change un jour de mode de connexion.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base déclarative commune — toute table du projet en hérite."""
    pass


def get_db() -> Session:
    """Dépendance FastAPI : une session DB par requête, toujours fermée après usage."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
