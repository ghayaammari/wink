# Wink

**Plateforme intelligente propulsée par l'IA générative pour l'accompagnement de l'écosystème startup (entrepreneurs, chercheurs, investisseurs).**

Contexte produit, schéma de données et architecture détaillés dans `docs/`.

---

## Sommaire

- [Contexte et problématique](#contexte-et-problématique)
- [Fonctionnalités](#fonctionnalités)
- [Système multi-agents](#système-multi-agents)
- [Système RAG](#système-rag)
- [Évaluation](#évaluation)
- [Stack technique](#stack-technique)
- [Installation](#installation)
- [Limites et perspectives](#limites-et-perspectives)

---

## Contexte et problématique

Créer une startup deeptech ou scientifique oblige l'entrepreneur à mener en parallèle des démarches administratives, des obligations réglementaires complexes (RGPD, AI Act, exigences sectorielles) et la recherche de partenaires stratégiques : chercheurs et investisseurs. Les sources officielles (Légifrance, CNIL, INPI, Guichet Unique) sont dispersées, ce qui fait perdre du temps, génère des coûts de conseil évitables et expose à des erreurs de conformité.

Le même manque de mise en relation contextualisée touche les deux autres acteurs :

- le **chercheur** n'a pas de canal structuré pour valoriser ses travaux auprès de startups ayant un besoin concret ;
- l'**investisseur** fait un sourcing manuel, sans vue d'ensemble fiable.

**Problématique : comment centraliser et fiabiliser cet accompagnement ?**

Wink y répond avec un copilot conversationnel qui répond, oriente et redirige l'utilisateur vers l'espace adapté, appuyé par des agents spécialisés dont chaque réponse est ancrée dans des sources vérifiables.

---

## Fonctionnalités

### Entrepreneur

- **Copilot conversationnel** : questions libres en langage naturel, routage automatique vers le bon domaine, génération de rapports téléchargeables en PDF.
- **Diagnostics de conformité** : RGPD, AI Act, conformité sectorielle (HealthTech, FinTech), certification SecNumCloud, avec obligations justifiées par des extraits du corpus réglementaire et score de conformité.
- **Analyse d'impact (AIPD)** générée à partir du diagnostic RGPD.
- **Démarches administratives** : forme juridique, statuts, immatriculation, annonce légale.
- **Mise en relation avec des chercheurs** : dépôt d'un besoin scientifique, feed de chercheurs classés avec explication de la pertinence.
- **Recommandation d'offres d'investissement** pour son projet.
- **Pitch deck** de 11 diapositives généré à partir d'un formulaire, éditable dans l'éditeur intégré.

### Chercheur

- Dépôt de travaux de recherche pour alimenter son profil.
- Résumés générés automatiquement, **validés par le chercheur** avant toute utilisation par le matching.
- Visibilité auprès des startups via le matching.

### Investisseur

- Définition de sa thèse d'investissement et dépôt d'offres de financement (montant, secteurs, stades).
- Feed de startups classées par pertinence, avec un score justifié.
- Marquage des startups « intéressantes ».

### Besoins non fonctionnels

Fiabilité et traçabilité des sources, transparence des scores, sécurité et confidentialité (séparation entre corpus réglementaire public et données des projets), personnalisation, évolutivité.

---

## Système multi-agents

Un **copilot orchestrateur** reçoit chaque question, la classe puis la délègue à l'agent compétent, répond, et redirige vers l'espace adapté si nécessaire. Tous les agents partagent le même moteur (LangGraph, agents ReAct, Groq) : seuls le prompt, les outils et le schéma de sortie changent.

| Agent | Rôle | Outils |
|---|---|---|
| **Copilot orchestrateur** | Point d'entrée conversationnel, délègue à l'agent administratif ou à sa branche conformité | Outils de conformité, lecture des résultats de matching (lecture seule) |
| **Agent de conformité** | Détection de secteur, RGPD, AI Act, écarts HealthTech et FinTech, SecNumCloud | Recherche dans le corpus réglementaire (RAG), lecture du profil du projet, lecture des diagnostics existants |
| **Agent administratif** | Création d'entreprise et démarches | Recherche dans le corpus administratif (RAG), profil du projet, progression de la roadmap, vérifications existantes |
| **Agent de matching chercheur** | Mise en correspondance d'un besoin scientifique avec les chercheurs | Lister les chercheurs, expertises passées, travaux confirmés, détail d'un travail |
| **Agents de matching startups / offres** | Mise en correspondance startups et offres de financement | Lister et détailler les projets, lister et détailler les offres |

Les agents de matching sont déclenchés explicitement par l'utilisateur depuis son espace, jamais en cascade automatique.

### Raisonnement ReAct

À chaque tour, l'agent **réfléchit** : s'il lui manque une information, il appelle un **outil**, **observe** le résultat puis recommence ; s'il a assez d'éléments, il produit une réponse structurée. Une limite d'itérations fixée à l'avance évite les boucles infinies.

### Règles anti-hallucination

- Aucune obligation ou classification n'est produite sans extrait du corpus réellement consulté : l'absence de couverture donne une **liste vide**, jamais une invention.
- Un champ de questionnaire non renseigné n'est jamais traité comme une réponse négative.
- Toute source citée est **vérifiée a posteriori** : elle doit correspondre à un extrait effectivement retourné par l'outil de recherche.
- Aucun outil d'écriture ni de recherche web n'est donné aux agents.

---

## Système RAG

Le retrieval repose sur un mécanisme unique : similarité cosinus sur des embeddings **BGE-M3** stockés dans **pgvector**, filtrée par domaine, sur les 8 résultats les plus proches.

**Construction du corpus**

1. Collecte et extraction (Légifrance, CNIL, MDR, ANSSI, guides administratifs).
2. Nettoyage minimal du texte.
3. Filtre de pertinence et classification par le LLM (sous-thème, stratégie de découpage), **validées par un humain** : le modèle ne modifie jamais le texte source.
4. Chunking adapté au type de texte (article court, alinéas, paragraphes regroupés).
5. Embedding avec BGE-M3, exécuté en local.
6. Indexation dans pgvector avec texte, vecteur, source, méthode de chunking et domaine.

**Recherche** : question de l'agent, embedding, filtre par domaine (`rgpd`, `ai_act`, `forme_juridique`, `secteur_healthtech`, `certification_secnumcloud`...), similarité cosinus, top 8, retour à l'agent.

Pas de recherche hybride ni de reformulation de requête : un choix volontairement simple, mesuré avant d'envisager plus de complexité.

---

## Évaluation

### Retrieval

Mesuré sur un **golden set de 59 questions** (question → chunk source attendu), réparties selon le volume de chunks par domaine.

| Métrique | Sans reranking | Avec reranking |
|---|---|---|
| Recall@8 | 98,31 % | n/a |
| MRR | **0,749** | 0,649 |

Le Recall@8 reste supérieur à 95 % sur tous les domaines. Un reranking par cross-encoder a été testé puis **rejeté** : il dégradait la MRR sur 4 domaines sur 5. Le point faible initialement identifié (`forme_juridique`, MRR = 0,379 sur 4 questions) s'est révélé surestimé sur l'échantillon complet de 12 questions (MRR = 0,689).

### Agents

- **LangSmith** : traçage et observabilité (agent délégué, outils appelés).
- **Human in the loop** : relecture et validation manuelle des sorties.
- **LLM-as-judge** : appliqué de façon limitée.

---

## Stack technique

| Couche | Technologies |
|---|---|
| Frontend | React, Vite, TypeScript, Tailwind CSS, React Router |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Swagger (OpenAPI) |
| Agents | LangGraph (agents ReAct), Groq (modèle `openai/gpt-oss-120b`), LangSmith |
| RAG | FlagEmbedding (BGE-M3, local), pgvector |
| Données | Supabase (PostgreSQL managé), Cloudinary |
| Authentification | Email / mot de passe et Google (OAuth), jeton JWT |

---

## Installation

### Prérequis

- **Python 3.11+** (voir le commentaire en tête de `backend/requirements.txt` sur les bornes de version).
- **Node.js 22+** et npm.
- **poppler** installé sur la machine (requis par `pdf2image` pour l'extraction de document) :
  - Windows : télécharger poppler, puis renseigner `POPPLER_PATH` dans `backend/.env` (chemin vers le dossier `Library/bin`).
  - macOS : `brew install poppler`.
  - Linux : `apt install poppler-utils` (ou équivalent).
- Un projet **Supabase** (PostgreSQL) avec l'extension `pgvector` activée, ou toute base Postgres accessible.
- Une clé API **Groq** (console.groq.com) : agents et extraction de document.
- Un **Client ID Google OAuth** : connexion « Se connecter avec Google » (optionnel : sans clé, l'auth Google est désactivée proprement, pas de crash).
- Un compte **Cloudinary** : stockage des fichiers (documents, logos).
- Un **SMTP** (optionnel : sans clé, « mot de passe oublié » est désactivé proprement).
- Une clé **LangSmith** (optionnel : traçage uniquement).

### 1. Backend (`backend/`)

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

#### Migrations de base de données

```bash
# toujours depuis backend/, avec le venv activé
alembic upgrade head
```

#### Lancer le serveur

Le serveur se lance **depuis `wink/`** (le dossier parent de `backend/`), pas depuis `backend/` : c'est nécessaire pour que `backend`, `agents` et `scrapers` soient importables.

```bash
cd ..   # revenir à wink/
uvicorn backend.main:app --reload
```

API disponible sur `http://localhost:8000`.

> `--reload` ne surveille pas les fichiers `.yaml` : après une modification de `agents/config/prompts.yaml`, redémarrer complètement le serveur.

### 2. Frontend (`frontend/`)

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

### 3. Agents (`agents/`)

Rien à lancer séparément : les agents sont appelés directement par le backend. La config des modèles LLM/VLM est centralisée dans `agents/config/llm_config.yaml`, et les prompts dans `agents/config/prompts.yaml`.

### 4. Construction du corpus RAG

Lancer le pipeline d'ingestion (collecte, classification, chunking, embedding) puis vérifier l'indexation dans pgvector. *À documenter avec les scripts réels du dépôt.*

### Vérifier que tout tourne

1. Backend : `http://localhost:8000/docs` doit afficher la doc Swagger FastAPI.
2. Frontend : `http://localhost:5173` doit afficher l'app et pouvoir appeler l'API (CORS configuré pour ces deux ports par défaut, ajustable via `CORS_ALLOWED_ORIGINS` côté backend).
3. Créer un compte (email ou Google si configuré) pour vérifier la chaîne DB + auth de bout en bout.

---

## Limites et perspectives

**Non réalisé à ce stade**

- Agent dédié aux contrats commerciaux.
- Côté investisseur : prise de contact par email et suivi en pipeline personnel.
- Côté chercheur : extraction automatique via ORCID/HAL (squelette technique seulement) et réception d'une proposition de collaboration (notification, messagerie).

**Pistes d'évolution**

- Protocoles standardisés de communication inter-agents (**A2A**) et d'accès aux outils (**MCP**), rendus possibles par le découpage actuel entre orchestrateur, agents et outils construits dynamiquement.
- Copilot dédié au chercheur.
- Évaluation chiffrée des agents (routage, appels d'outils, ancrage dans les sources).
