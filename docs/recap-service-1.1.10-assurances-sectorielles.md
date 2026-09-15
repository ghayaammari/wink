# Récapitulatif — Service 1.1.10 (Orientation sectorielle vers les assurances obligatoires)

Service 1.1.10 du Groupe 2 (Incrément 1, EPIC-01) : collecte des recommandations d'assurance par secteur d'activité startup (base légale + guides professionnels), classification, validation humaine, découpage et vectorisation pour le copilot. Ce document couvre tout ce qui a été implémenté, fichier par fichier, avec le rôle de chaque fonction clé.

Architecture pensée dès le départ pour être **modulaire et indépendante** du pipeline forme juridique (service 1.1.1) : aucun fichier existant du pipeline `legal_texts` n'a été modifié pour ce service, seulement réutilisé tel quel quand la fonction était déjà générique.

Périmètre : **11 secteurs startup**, chacun avec un profil d'assurance distinct (voir table d'alias plus bas pour les secteurs rattachés sémantiquement).

---

## Décision préalable — collecte à l'avance, pas de recherche à la volée

Choix tranché avant l'implémentation : **batch + validation humaine**, jamais de génération live par secteur utilisateur. Raisons principales :
- La contrainte anti-hallucination du projet ("aucune réponse réglementaire sans source précise et vérifiable") ne peut pas être garantie par un LLM en direct sans relecture humaine préalable.
- Le schéma (`statut_contenu extrait_automatique → valide_humain`) est conçu pour du contenu validé une fois, pas pour du cache de requête.
- Les obligations d'assurance par secteur changent rarement — même logique que le corpus `legal_texts`.

Pour un secteur hors périmètre : repli explicite ("secteur pas encore couvert") + log de la demande, jamais de réponse générée à la volée.

---

## Modèle et périmètre sectoriel

### `backend/shared/knowledge_base/models/sector_insurance_recommendations.py`

Table cible. Colonnes clés : `secteur`, `type_assurance`, `a_base_legale` (bool, jamais présumé par défaut), `legal_text_id` (FK optionnelle vers `legal_texts`, remplie seulement côté base légale), `source_nom`/`source_url`/`texte_brut` (côté non-légal), `statut_contenu` (`extrait_automatique` | `valide_humain`), `collecte_le`, `derniere_verification`.

### 11 secteurs collectés

SaaS/Tech générique, FinTech, HealthTech, E-commerce/Marketplace, Conseil/Services professionnels, GreenTech/CleanTech/Énergie, DeepTech Hardware/Robotique/IoT, Mobilité/Transport/Logistique, AgriTech/FoodTech, Construction Tech/PropTech, Industrie/Manufacturing.

### `SECTOR_ALIASES` (dans `scrapers/legifrance/blocs_secteurs_assurance.py`)

6 secteurs rattachés sémantiquement plutôt que collectés séparément (pas de profil d'assurance distinct) : Intelligence Artificielle, Cybersécurité, EdTech, Gaming, Media → SaaS/Tech générique ; Legal Tech, RH Tech → Conseil/Services professionnels ; InsurTech → FinTech.

`Project.sector` étant un champ texte libre non contraint côté entrepreneur, le matching secteur utilisateur → entrée collectée devra être sémantique (embedding/LLM), jamais une égalité exacte — point identifié, matching à implémenter au moment du service utilisateur final (hors périmètre de cette collecte).

---

## Volet 1 — Collecte base légale (Légifrance)

### `scrapers/legifrance/blocs_secteurs_assurance.py`

Pure donnée, même forme que `blocs_formes_juridiques.py` mais fichier distinct (SRP). Dataclass `BlocAssurance` : **8 blocs** Légifrance, chacun avec `secteurs_concernes` fixé à l'avance (jamais deviné par le LLM) :
- Code des assurances — RC Pro générale (transversal aux 11 secteurs), assurance décennale (Construction), assurance auto obligatoire (Mobilité)
- Code de la santé publique — RC Pro santé (HealthTech)
- Code monétaire et financier — RC Pro IOBSP **et** RC Pro CIF (FinTech, 2 blocs distincts — sous-arbres différents du code)
- Code de l'environnement — responsabilité environnementale (GreenTech)
- Code civil — RC produit défectueux, art. 1245 s. (DeepTech, Industrie, AgriTech)

**Identifiants LEGISCTA corrigés le 2026-09-11** : la première version contenait des identifiants devinés depuis les URLs publiques legifrance.gouv.fr, non vérifiés — le premier run réel a échoué (`Section '...' introuvable`). Corrigés en interrogeant l'API `consult/legiPart` directement (dump de l'arbre des sections) et en vérifiant que chaque section contient bien l'article de référence attendu (L211-1, L241-1, L1142-2, L519-3-4, L541-3, L161-1, art. 1245). Au passage : le bloc RC Pro générale était sur le mauvais Titre (Titre I au lieu de Titre II), et IOBSP/CIF se sont révélés être dans deux sous-arbres distincts du Code monétaire et financier plutôt qu'un seul bloc commun — d'où le passage de 7 à 8 blocs.

### `scrapers/legifrance/legifrance_client.py` (réutilisé tel quel)

Aucune modification : `fetch_articles_in_block(source_id, section_id)` ne connaît que l'API Légifrance, déjà découplé de `legal_texts` — directement réutilisable pour le volet assurance.

### `agents/ingestion/sector_insurance_structuring_service.py`

Fichier dédié (ne modifie pas `legal_text_structuring_service.py`). Un seul appel LLM (Groq) par texte × secteur :

- **`classify_insurance_text(texte_brut, secteur)`** — produit `type_assurance` (ex: RC Pro, décennale, cyber), `a_base_legale` (`true` uniquement si une référence légale explicite est identifiée dans le texte — jamais présumé par défaut), et `chunking_suggere`.
- **`_create_completion_with_backoff()`** — même logique de retry sur 429 que le pipeline forme juridique (dette mineure assumée, code dupliqué plutôt que factorisé — voir "règle de 3" évoquée dans le fichier source).

Config : `agents/config/llm_config.yaml` / `agents/config/prompts.yaml`, nouvelle section top-level `sector_insurance_structuration:` (ajout additif, aucune clé existante modifiée).

### `backend/shared/knowledge_base/scripts/collect_sector_insurance_recommendations.py`

Orchestrateur Phase 1 (volet légal uniquement). Pour chaque bloc → fetch Légifrance → pour chaque article × chaque secteur concerné → classification LLM → upsert en `extrait_automatique`. **Commit par bloc**, même convention que `collect_legal_texts_formes_juridiques.py`.

---

## Volet 2 — Collecte web du volet non-légal (guides professionnels)

**Deuxième tentative, reconstruite depuis zéro après suppression de la première** (contenu rédigé à la main plutôt que réellement extrait — voir historique). Cette fois, `texte_brut` ne peut provenir que d'une vraie page effectivement récupérée : aucun LLM ni humain n'écrit de contenu, le LLM ne fait que filtrer et classifier du texte déjà extrait.

### `scrapers/shared/web_fetch.py` (nouveau — infra générique, source-agnostique)

Parle au web de façon polie et traçable, sans aucune notion d'assurance/secteur (SRP), réutilisable par tout futur scraper HTML.

- **`fetch_page(url)`** — orchestrateur : vérifie `robots.txt` (`is_allowed_by_robots`) → respecte un délai minimum par domaine (`_respect_rate_limit`, 2s) → `requests.get()` avec `User-Agent` identifiant → extraction via `trafilatura` (HTML) ou `pypdf` (PDF, détecté par `Content-Type`/extension — réutilise la dépendance déjà présente pour `research_extraction_service.py`, pas de nouvelle lib PDF) → cache mémoire par URL. Ne lève jamais d'exception : renvoie `None` sur tout échec, pour que l'orchestrateur appelant passe simplement à la page suivante.
- **`discover_links(html_brut, base_url, max_links)`** — extraction des `<a href>` via BeautifulSoup, résolution des URLs relatives, **filtrage strict au même domaine** (condition du crawling borné), plafonné à `max_links`.
- **Bug corrigé en cours de route** : `is_allowed_by_robots()` ne peut pas utiliser `RobotFileParser.read()` tel quel — celui-ci fetch `robots.txt` via `urllib.request` avec un `User-Agent` générique, que le pare-feu anti-bot de `franceassureurs.fr` bloquait (403), faisant interpréter (à tort) tout le site comme interdit par `robotparser`. Corrigé en récupérant `robots.txt` nous-mêmes via `requests` (notre `User-Agent`) puis en passant le contenu à `parser.parse()`.

### `scrapers/shared/page_seed.py`

Dataclass `PageSeed` (`url`, `secteurs_cibles` fixé par curation humaine — jamais deviné par le LLM, `max_liens_a_suivre` pour le crawling borné profondeur 1).

### Sources retenues (curées et vérifiées manuellement le 2026-09-11, pas devinées)

| Dossier | Source | URL(s) de départ vérifiées | Secteurs ciblés |
|---|---|---|---|
| `scrapers/bpifrance/pages_assurance.py` | Bpifrance Création | `bpifrance-creation.fr/moment-de-vie/assurer-mon-entreprise` | SaaS, E-commerce, Conseil |
| `scrapers/france_assureurs/pages_assurance.py` | France Assureurs (FFA) | Guide PDF "15 réflexes pour bien s'assurer" + page presse qui l'annonce | SaaS, E-commerce, Mobilité, Industrie, Conseil |
| `scrapers/cci_paris_idf/pages_assurance.py` | CCI Paris Île-de-France | Fiche pratique "carte professionnelle loi Hoguet" (cite explicitement l'obligation RC Pro agents immobiliers) | Construction Tech/PropTech |

`swim.legal` **définitivement exclu** (blog juridique tiers, ni source officielle ni organisme professionnel reconnu — décision validée avec l'utilisateur).

Chaque URL a été récupérée et son contenu inspecté avant d'être ajoutée ici (pas de contenu inventé) — voir le commentaire "Vérifié manuellement" en tête de chaque fichier `pages_assurance.py`. Le crawling borné a déjà démontré son intérêt en test : depuis la page presse France Assureurs, il découvre automatiquement `lassurance-pour-les-professionnels/`, une page pertinente non listée à la main.

### Extension additive de `agents/ingestion/sector_insurance_structuring_service.py`

- **`filter_page_relevance(secteur, titre, extrait)`** (nouveau) — même schéma deux-étapes que `filter_article_relevance()` du pipeline forme juridique : filtre bon marché (titre + ~500 premiers caractères d'une page réellement récupérée) avant l'appel de classification complet. Config additive : `sector_insurance_structuration.page_relevance` dans `llm_config.yaml`/`prompts.yaml`.
- `classify_insurance_text()` (déjà existante) reste inchangée, appelée uniquement sur les pages ayant passé le filtre.

### `backend/shared/knowledge_base/scripts/collect_sector_insurance_pages.py` (nouveau, remplace l'ancien `seed_sector_insurance_non_legal.py`)

Orchestrateur. Pour chaque source : pour chaque `PageSeed` → `fetch_page()` sur l'URL de départ → `discover_links()` (borné par `max_liens_a_suivre` et par `MAX_PAGES_PER_SOURCE = 15` global) → pour chaque page candidate × chaque secteur ciblé → `filter_page_relevance()` puis, si pertinent, `classify_insurance_text()` → `upsert_sector_insurance()` avec `texte_brut` = le texte réellement extrait par `fetch_page()`. Commit par source.

Ajouter une source = ajouter une entrée dans `SOURCES` (liste `(nom, pages)`) — aucune autre logique à modifier (Open/Closed), même principe que `BLOCS_ASSURANCE` pour le volet Légifrance.

### Nouvelles dépendances (`backend/requirements.txt`)

`trafilatura` (extraction contenu principal), `beautifulsoup4` + `lxml` (extraction de liens). `robots.txt` géré via `urllib.robotparser` (stdlib, aucune dépendance ajoutée). PDF via `pypdf`, déjà présent.

### Vérifié en conditions réelles (pas seulement `py_compile`)

- `fetch_page()` + `discover_links()` testés en direct sur les 3 sources : contenu réellement extrait et cohérent, `robots.txt` correctement respecté, cache et rate-limiting actifs.
- `filter_page_relevance()`/`classify_insurance_text()` : **non testés en conditions réelles dans cet environnement** — le module `groq` n'est pas installé localement (seulement `py_compile` a pu vérifier la syntaxe). À tester avant le premier vrai run.
- Écriture en base : **non testée** — `psycopg` absent de l'environnement local (la base tourne sur Supabase distant, même limitation déjà documentée pour le reste du projet).

---

## Persistance

### `backend/shared/knowledge_base/services/sector_insurance_recommendations_service.py`

Persistance pure, aucun appel IA/API — ne commit jamais (laissé à l'appelant), même convention que `legal_texts_service.py`.

- **`upsert_sector_insurance(...)`** — insère ou met à jour par `(secteur, type_assurance)`. Repasse en `extrait_automatique` uniquement si le contenu a réellement changé.
- **`list_valide_humain(db)`** / **`list_pending_validation(db)`** — lectures filtrées par `statut_contenu`.
- **`validate_sector_insurance(db, record_id, action)`** — `"valider"` passe en `valide_humain` sans y toucher ; `"corriger"` passe en `valide_humain` ET inverse `a_base_legale` (seule correction permise par ce dashboard).

---

## Validation humaine (dashboard)

### Backend

- **`backend/shared/knowledge_base/schemas/sector_insurance_schemas.py`** — `SectorInsuranceValidationItem` (réponse), `SectorInsuranceValidationAction` (`"valider"` | `"corriger"`).
- **`backend/shared/knowledge_base/routes/sector_insurance_validation_router.py`**
  - `GET /knowledge-base/sector-insurance/pending-validation` — liste les lignes `extrait_automatique`, calcule `longueur_caracteres` à la volée.
  - `PATCH /knowledge-base/sector-insurance/{id}/validation` — applique l'action.
  - Protégé par `get_current_user`, même dette technique que `legal_texts_validation_router.py` (pas de rôle admin dans le système).
- **`backend/main.py`** — router enregistré (ajout additif).

### Frontend

- **`frontend/src/admin/api/sectorInsuranceValidationApi.ts`** — client HTTP dédié.
- **`frontend/src/admin/pages/SectorInsuranceValidationPage.tsx`** — une carte par recommandation (secteur, type_assurance, badge Base légale/Recommandation, source, texte), boutons Valider/Corriger.
- **`frontend/src/App.tsx`** — route `/admin/sector-insurance` (ajout, aucune route existante touchée).

---

## Chunking + Embedding

### `agents/ingestion/legal_text_chunking_service.py` / `agents/ingestion/embedding_service.py` (réutilisés tels quels)

Fonctions pures et génériques déjà écrites pour `legal_texts`, aucune modification nécessaire.

### `backend/shared/knowledge_base/models/content_embeddings.py`

Contrainte `ck_content_embeddings_domaine` élargie pour accepter `'assurance_sectorielle'` (migration `a7b3c8d1e4f2`).

### `backend/shared/knowledge_base/scripts/chunk_and_embed_sector_insurance.py`

Orchestrateur Phase 2+3, même pattern que `chunk_and_embed_legal_texts.py`. Lit les lignes `valide_humain` dont `texte_brut` n'est pas vide → chunk (méthode `"aucun"`, un seul chunk par recommandation — pas d'alinéas ici) → un seul appel groupé à `embed_texts()` → upsert avec `source_type="sector_insurance_recommendations"`, `champ_source="texte_brut"`, `domaine="assurance_sectorielle"`. Transaction unique, commit à la fin.

---

## Migration

### `backend/alembic/versions/a7b3c8d1e4f2_add_sector_insurance_recommendations.py`

Revises `6f1a2c9d3e5b`. Crée la table `sector_insurance_recommendations` + élargit `ck_content_embeddings_domaine` pour ajouter `'assurance_sectorielle'`.

---

## Architecture modulaire (SOLID)

Contrainte explicite du projet : pouvoir supprimer/modifier tout le pipeline assurance sans risque de régression sur le pipeline forme juridique (75 articles, déjà en prod), et inversement.

**Fichiers neufs, zéro dépendance vers le code spécifique `legal_texts`** : tous les fichiers listés ci-dessus sous `scrapers/legifrance/blocs_secteurs_assurance.py`, `agents/ingestion/sector_insurance_structuring_service.py`, `backend/shared/knowledge_base/{models,services,schemas,routes,scripts}/sector_insurance*`, `frontend/src/admin/{api,pages}/sectorInsurance*`.

**Fichiers existants réutilisés sans modification** (déjà génériques) : `legifrance_client.py`, `legal_text_chunking_service.py`, `embedding_service.py`, `content_embeddings_service.py`.

**Modifications additives uniquement** (rien de supprimé/changé) : `agents/config/{prompts,llm_config}.yaml` (nouvelle section top-level), `backend/shared/knowledge_base/models/__init__.py` (import + `__all__`), `backend/main.py` (router), `frontend/src/App.tsx` (route), migration Alembic (fichier neuf, pas d'édition de `content_embeddings.py`).

Conséquence : supprimer le pipeline assurance = supprimer les fichiers `sector_insurance_*`/`recommandations_assurance.py` + revenir sur 4 ajouts additifs facilement identifiables — zéro risque sur `legal_texts`/forme juridique.

---

## État actuel

Implémenté : modèle, persistance, dashboard de validation (back + front), classification LLM, collecte Légifrance (volet base légale), collecte web du volet non-légal (infra `web_fetch.py` + 3 sources vérifiées, voir "Volet 2"), chunking + embedding, migration.

**Pas encore exécuté / vérifié en conditions réelles** :
- Lancement effectif de `collect_sector_insurance_recommendations.py` (volet Légifrance) — identifiants LEGISCTA à vérifier par un vrai appel API avant la première collecte, même précaution que pour `blocs_formes_juridiques.py`.
- Lancement effectif de `collect_sector_insurance_pages.py` (volet non-légal) — `fetch_page()`/`discover_links()` vérifiés en réel, mais `filter_page_relevance()`/`classify_insurance_text()` (Groq) et l'écriture en base (Supabase) pas testées dans cet environnement local (`groq` et `psycopg` absents) — seulement `py_compile`.
- Seulement 3 sources/4 pages de départ couvrent 4 des 11 secteurs pour l'instant (SaaS, E-commerce, Conseil, Mobilité, Industrie, Construction/PropTech partiellement) — FinTech, HealthTech, GreenTech, DeepTech, AgriTech pas encore couverts par ce volet (le volet Légifrance peut déjà les couvrir partiellement). Ordres professionnels spécifiques (santé, experts-comptables...) pas encore sourcés.
- Validation humaine effective des lignes collectées (dashboard prêt, contenu pas encore relu).
- Lancement de `chunk_and_embed_sector_insurance.py`.
- Test de retrieval sur une vraie question utilisateur.

## Dette technique / points non tranchés

- Couverture sectorielle du volet non-légal encore partielle (voir liste ci-dessus) — à étendre en ajoutant des `PageSeed` vérifiées, jamais en devinant des URLs.
- Pas de rôle admin dans le système — dashboard accessible à tout compte connecté (même dette que le pipeline forme juridique).
- Matching secteur utilisateur (texte libre `Project.sector`) → secteur collecté : pas encore implémenté, nécessitera une classification sémantique avec seuil de confiance (en dessous, traiter comme non couvert).
- Comportement du service 1.1.10 pour un secteur hors périmètre (message + file de collecte) : cadré dans le plan initial, pas encore codé — dépend du service utilisateur final, hors périmètre de cette collecte de corpus.
- Logique de retry Groq dupliquée entre `sector_insurance_structuring_service.py` et `legal_text_structuring_service.py` — factorisation différée tant qu'un 3e pipeline n'apparaît pas.
