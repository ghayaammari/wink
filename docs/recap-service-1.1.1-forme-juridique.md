# Récapitulatif — Service 1.1.1 (Forme juridique), Phases 1 à 3

Service 1.1.1 du Groupe 2 : collecte du corpus juridique (Code de commerce, formes SAS/SASU/SARL/EURL), classification, découpage et vectorisation pour la recherche sémantique du futur copilot. Ce document couvre tout ce qui a été implémenté, phase par phase, avec le rôle de chaque fichier et fonction clé.

Périmètre final (recentré depuis une version initiale à 14 blocs) : **3 blocs** du Code de commerce couvrant SAS, SASU, SARL, EURL — 75 articles collectés.

---

## Phase 1 — Collecte

### `scrapers/legifrance/blocs_formes_juridiques.py`

Pure donnée, aucune logique. Définit les 3 blocs à collecter (dataclass `BlocLegifrance`) : identifiants Légifrance (`legifrance_source_id`, `legifrance_section_id`), `domaine_reglementaire`, et **`forme_juridique_concernee` fixe par bloc** (`['SAS','SASU','SARL','EURL']` pour le Titre I, `['SARL','EURL']` pour le Chapitre III, `['SAS','SASU']` pour le Chapitre VII) — jamais devinée par le LLM article par article, puisque chaque bloc correspond déjà à des formes connues d'avance.

### `scrapers/legifrance/legifrance_client.py`

Parle à l'API PISTE/Légifrance, rien d'autre (aucune notion de `legal_texts`, aucun LLM).

- **`_get_token()`** — auth OAuth2 `client_credentials`, token mis en cache en mémoire process.
- **`_fetch_text(legifrance_source_id)`** — récupère le texte ENTIER (ex: tout le Code de commerce) via `consult/legiPart`, mis en cache par `source_id`. Fait exprès : un identifiant de section passé en entrée ne scope pas la réponse (vérifié par un vrai appel — demander la section SAS/SASU a renvoyé les 7334 articles du Code entier). Donc un seul appel par texte source, jamais par bloc.
- **`_find_section(node, section_id)`** — cherche récursivement, dans l'arbre déjà récupéré, la section précise (par `id`/`cid`) : c'est ce qui permet d'extraire localement le bon bloc après un seul fetch.
- **`_collect_articles(node)`** — collecte récursivement tous les articles `etat="VIGUEUR"` (un article abrogé n'intéresse pas un entrepreneur qui crée sa société aujourd'hui).
- **`strip_html(raw)`** — nettoie le HTML du champ `content` (balises, entités `&eacute;`...). **Corrigé le 10/09/2026** : remplace maintenant `</p>`/`<br>` par un saut de ligne AVANT de retirer les autres balises — sinon deux alinéas se retrouvaient collés sans espace ni frontière (bug réel détecté sur L.227-10, 4 alinéas fusionnés en un seul bloc), cassant tout découpage par alinéa en Phase 2.
- **`fetch_articles_in_block(source_id, section_id)`** — point d'entrée public : fetch (caché) + extraction de section + collecte des articles.

### `agents/config/prompts.yaml` + `agents/ingestion/legal_text_structuring_service.py`

Deux appels LLM (Groq) par article, jamais sur le texte lui-même :

- **`filter_article_relevance(texte_brut)`** — écarte les articles hors-sujet (pas un des sous-thèmes régime_social/gouvernance/fiscalité/responsabilité/capital_social) avant classification.
- **`classify_article(texte_brut)`** — produit `sous_theme` + `chunking_suggere` (`"aucun"` ou `"par_alinea"`, jugement sémantique du LLM : les alinéas traitent-ils d'un seul sujet ou de sujets distincts). Ne produit plus `forme_juridique_concernee` (fixée par bloc, voir plus haut).
- **`_create_completion_with_backoff()`** — retry avec délai croissant sur 429 (limite de débit Groq), distinct du retry sur JSON invalide de `_call_llm()`.

### `backend/shared/knowledge_base/models/legal_texts.py`

Table cible. Colonnes clés : `code_source`, `article_numero` (clé naturelle unique ensemble), `texte_brut`, `sous_theme`, `forme_juridique_concernee` (array), `chunking_suggere`, `statut_contenu` (`extrait_automatique` | `valide_humain`).

### `backend/shared/knowledge_base/services/legal_texts_service.py`

Persistance pure, aucun appel IA/API externe.

- **`upsert_legal_text(...)`** — insère ou met à jour par `(code_source, article_numero)`. Repasse `statut_contenu` à `extrait_automatique` UNIQUEMENT si le contenu a réellement changé — une validation humaine faite sur l'ancien texte ne garantit rien sur le nouveau.
- **`update_texte_brut(...)`** — met à jour SEULEMENT `texte_brut` (et `date_effet`), jamais la classification — utilisée pour corriger le texte source sans reclassifier (donc sans appel LLM).
- **`list_pending_validation(db)`** / **`list_valide_humain(db)`** — lectures filtrées par `statut_contenu`, consommées respectivement par le dashboard (Phase 1.5) et le chunking (Phase 2).

### `backend/shared/knowledge_base/scripts/collect_legal_texts_formes_juridiques.py`

Orchestrateur. Pour chaque bloc : fetch → filtre pertinence → classification → upsert. **Commit par bloc** (3 transactions séparées, pas une seule globale) : un échec sur un bloc garde les blocs précédents déjà commités.

---

## Phase 1.5 — Validation humaine (dashboard)

Relecture humaine avant de faire confiance à une ligne pour le chunking/embedding — rien ne passe en `valide_humain` sans passer par ce dashboard.

### Backend

- **`backend/shared/knowledge_base/schemas/legal_texts_schemas.py`** — `LegalTextValidationItem` (réponse), `LegalTextValidationAction` (`"valider"` | `"corriger"`).
- **`backend/shared/knowledge_base/routes/legal_texts_validation_router.py`**
  - `GET /knowledge-base/legal-texts/pending-validation` — liste les lignes `extrait_automatique`, calcule `longueur_caracteres`/`nb_alineas_detectes` à la volée (jamais stockés — dérivés de `texte_brut`, affichés une fois, pas besoin de colonne à resynchroniser).
  - `PATCH /knowledge-base/legal-texts/{id}/validation` — "valider" passe en `valide_humain` sans toucher `chunking_suggere` ; "corriger" passe en `valide_humain` ET inverse `chunking_suggere` (`aucun` ↔ `par_alinea`).
  - Protégé par authentification simple (`get_current_user`), pas de rôle admin dans le système — dette technique assumée.

### Frontend

- **`frontend/src/admin/api/legalTextsValidationApi.ts`** — client HTTP.
- **`frontend/src/admin/pages/LegalTextsValidationPage.tsx`** — une carte par article (texte, longueur, alinéas détectés, suggestion), boutons Valider/Corriger. Page autonome, pas de `DashboardLayout`/`Sidebar` (construits autour du profil par acteur, sans usage ici).
- **`frontend/src/App.tsx`** — route `/admin/legal-texts`, accès à tout compte connecté (pas de rôle admin existant).

---

## Phase 2 — Chunking

### `agents/ingestion/legal_text_chunking_service.py`

Fonction pure, aucun accès DB, aucun appel LLM — la décision de méthode est déjà prise (Étape 1.4 + confirmée par le dashboard), ce module l'applique seulement.

- **`chunk_texte_brut(texte_brut, chunking_suggere)`** :
  - `"aucun"` → `[texte_brut]` (1 seul chunk, l'article entier).
  - `"par_alinea"` → découpe sur double saut de ligne (`\n\n`) ou numérotation `1°`/`2°`/`3°` en début de ligne. Si aucun séparateur trouvé malgré `"par_alinea"`, retombe sur 1 chunk plutôt que planter (garde-fou, cohérent avec `nb_alineas_detectes` déjà documenté "pas fiable à 100%").

Pas de table intermédiaire : un chunk n'existe qu'au moment de son insertion en Phase 3.

---

## Phase 3 — Embedding

### `agents/ingestion/embedding_service.py` (réutilisé tel quel, écrit pour le Groupe 1)

- **`embed_texts(textes: list[str]) -> list[list[float]]`** — un vecteur dense par texte, via BGE-M3 en local (`FlagEmbedding`, mode Dense uniquement, dimension 1024). Modèle chargé une seule fois par process (singleton).

### `backend/shared/knowledge_base/models/content_embeddings.py`

Magasin vectoriel générique, partagé entre toutes les sources (`roadmap_node`, `legal_texts`...). Contrainte `ck_content_embeddings_domaine` élargie cette session pour accepter `'forme_juridique'`/`'statuts_societe'` (migration `6f1a2c9d3e5b`).

### `backend/shared/knowledge_base/services/content_embeddings_service.py` (réutilisé tel quel)

- **`upsert_embedding(...)`** — insère ou remplace par `(source_type, source_id, chunk_index)` : relancer après une correction de texte ne crée jamais de doublon.

### `backend/shared/knowledge_base/scripts/chunk_and_embed_legal_texts.py`

Orchestrateur Phase 2+3 en un seul script. Lit les lignes `valide_humain` → chunke chacune → un seul appel groupé à `embed_texts()` (tous les chunks de toutes les lignes) → upsert de chaque chunk avec `source_type="legal_texts"`, `champ_source="texte_brut"`, `domaine=domaine_reglementaire`. Une seule transaction, commit unique à la fin (même convention que `seed_roadmap_nodes.py`, Groupe 1).

**Résultat du dernier run** : 75 articles traités → 155 chunks embeddés (57 articles `aucun` = 57 chunks + 18 articles `par_alinea` = 98 chunks).

---

## Bug trouvé et corrigé en cours de route

`strip_html()` retirait `</p>`/`<br>` sans les remplacer par un saut de ligne → deux alinéas HTML se retrouvaient collés en un seul bloc de texte, sans aucune frontière détectable. Conséquence : le découpage par alinéa de la Phase 2 ne trouvait jamais de séparateur, même sur les articles classés `"par_alinea"` par le LLM.

Diagnostiqué via un contrôle concret : 75 lignes `valide_humain` → 75 embeddings (1 par article, alors que 18 étaient censés se découper en plusieurs chunks).

Correctif appliqué en 4 temps (scripts jetables, supprimés après usage) :
1. Script de preview — refetch le HTML brut, applique un correctif candidat, écrit un JSON local (rien en base) pour relecture manuelle.
2. Après validation manuelle du JSON, MAJ ciblée de `texte_brut` en base pour les 18 lignes `par_alinea` uniquement (pas les 75 — décision explicite pour limiter la re-validation nécessaire).
3. Correctif définitif appliqué à `strip_html()` dans `legifrance_client.py` (pipeline permanent, toute future collecte en bénéficie).
4. Suppression des embeddings `chunk_method='par_alinea'` existants + revalidation des 18 lignes via le dashboard + nouveau `chunk_and_embed_legal_texts.py`.

---

## État actuel

Phases 1, 1.5, 2, 3 complètes et vérifiées (75 articles, 155 chunks). Reste de la **Phase 4 (vérification finale)** : test manuel de retrieval sur une vraie question (ex: "quel régime social pour un dirigeant de SARL ?") pour confirmer la pertinence des résultats avant de considérer la collecte vraiment terminée.

## Dette technique / points non tranchés

- Pas de rôle admin dans le système — le dashboard de validation et son endpoint sont accessibles à tout compte connecté.
- Emplacement frontend `frontend/src/admin/` : pas couvert par `Wink_architecture_fichiers.md` (aucun acteur ne correspond à un outil interne), décision prise en session, à documenter dans l'architecture si d'autres outils internes suivent.
- SCOP et micro-entreprise (CGI) : blocs volontairement laissés vides (identifiants non vérifiés / articles non contigus), hors périmètre tant qu'un besoin utilisateur confirmé n'apparaît pas.
