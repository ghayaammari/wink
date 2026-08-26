# Wink

Plateforme mettant en relation entrepreneurs, chercheurs et investisseurs. Contexte produit, schéma de données et architecture détaillés dans `docs/` et dans les fichiers `Wink_context_project.md` / `Wink_architecture_fichiers.md`.

Ce README couvre uniquement les étapes pour faire tourner le projet en local.

## Prérequis

- **Python 3.11+** (le venv actuel du projet utilise 3.14 — voir le commentaire en tête de `backend/requirements.txt` sur les bornes de version).
- **Node.js 22+** et npm.
- **poppler** installé sur la machine (requis par `pdf2image` pour l'extraction de document) :
  - Windows : télécharger poppler, puis renseigner `POPPLER_PATH` dans `backend/.env` (chemin vers le dossier `Library/bin`).
  - macOS : `brew install poppler`.
  - Linux : `apt install poppler-utils` (ou équivalent).
- Un projet **Supabase** (PostgreSQL) — ou toute base Postgres accessible.
- Une clé API **Groq** (console.groq.com) — extraction de document (agents).
- Un **Client ID Google OAuth** — connexion "Se connecter avec Google" (optionnel : sans clé, l'auth Google est désactivée proprement, pas de crash).
- Un compte **Cloudinary** (optionnel pour l'instant — décision actée mais pas encore consommée par le code).
- Un **SMTP** (optionnel — sans clé, "mot de passe oublié" est désactivé proprement).

## 1. Backend (`backend/`)

```bash
cd backend
python -m venv venv
# Windows : venv\Scripts\activate
# macOS/Linux : source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# remplir DATABASE_URL, JWT_SECRET_KEY (généré via la commande indiquée dans .env.example),
# GROQ_API_KEY, et le reste selon les fonctionnalités voulues
```

### Migrations de base de données

```bash
# toujours depuis backend/, avec le venv activé
alembic upgrade head
```

### Lancer le serveur

Le serveur se lance **depuis `wink/`** (le dossier parent de `backend/`), pas depuis `backend/` — c'est nécessaire pour que `backend`, `agents` et `scrapers` soient importables comme le veut l'architecture :

```bash
cd ..   # revenir à wink/
uvicorn backend.main:app --reload
```

API disponible sur `http://localhost:8000`.

## 2. Frontend (`frontend/`)

```bash
cd frontend
npm install

cp .env.example .env
# remplir VITE_API_BASE_URL (http://localhost:8000 par défaut) et VITE_GOOGLE_CLIENT_ID
```

```bash
npm run dev
```

App disponible sur `http://localhost:5173`.

## 3. Agents (`agents/`)

Rien à lancer séparément à ce stade — `agents/shared/document_processing/` est appelé directement par le backend (service d'import de document). La config des modèles LLM/VLM utilisés est centralisée dans `agents/config/llm_config.yaml`.

## 4. Scrapers (`scrapers/`)

Vides pour l'instant (prévus à partir de l'incrément I1) — rien à lancer.

## Vérifier que tout tourne

1. Backend : `http://localhost:8000/docs` doit afficher la doc Swagger FastAPI.
2. Frontend : `http://localhost:5173` doit afficher l'app et pouvoir appeler l'API (CORS déjà configuré pour ces deux ports par défaut, ajustable via `CORS_ALLOWED_ORIGINS` côté backend).
3. Créer un compte (email ou Google si configuré) pour vérifier la chaîne DB + auth de bout en bout.
