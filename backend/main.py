"""Point d'entrée FastAPI — assemble tous les routers du backend Wink.

Lancement : `uvicorn backend.main:app --reload` depuis `wink/` (le dossier
parent de `backend/`) — voir la note sys.path ci-dessous pour pourquoi.
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Même correctif que backend/alembic/env.py : rend `backend` importable quel
# que soit le dossier depuis lequel `uvicorn` est lancé (ce fichier est dans
# backend/, donc un seul niveau au-dessus = wink/, le parent de backend/,
# agents/, scrapers/... comme le veut l'architecture).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.entrepreneur.routes.document_router import router as document_router
from backend.entrepreneur.routes.project_router import router as project_router
from backend.shared.auth.routes.auth_router import router as auth_router
from backend.chercheur.routes.researcher_profile_router import router as researcher_profile_router
from backend.chercheur.routes.research_work_router import router as research_work_router
from backend.chercheur.routes.researcher_past_expertise_router import router as researcher_past_expertise_router
from backend.investisseur.routes.investor_router import router as investor_router


app = FastAPI(title="Wink API", version="0.1.0")
app.include_router(researcher_profile_router)
app.include_router(research_work_router)
app.include_router(researcher_past_expertise_router)
app.include_router(investor_router)

# CORS : nécessaire dès que le frontend (React, autre origine) appelle l'API
# depuis un navigateur. Liste lue depuis l'env, avec un défaut de dev
# raisonnable — à restreindre en prod via CORS_ALLOWED_ORIGINS (pas de "*"
# avec allow_credentials=True, le navigateur le refuse de toute façon).
_allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(project_router)
app.include_router(document_router)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Vérification rapide que l'API tourne — utile pour un futur monitoring/CI."""
    return {"status": "ok"}