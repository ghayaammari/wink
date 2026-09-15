# Récapitulatif — Service 1.1.11 (Plan d'action pré-création)

Service 1.1.11 du Groupe 1 (Incrément 1, EPIC-01) : roadmap visuelle des étapes de création d'une startup (24 nœuds, 5 groupes), suivi de progression par statut, déverrouillage en cascade le long du graphe de dépendances, dépôt de preuve documentaire par étape, et **filtrage à l'affichage** des étapes dont la pertinence dépend du profil réel du projet (`applicable_if`). V1 uniquement : pas de bouton "Explain more" (V2, copilot) ni de lancement direct d'un service EPIC-01 (V3) — périmètre acté dans "Wink — Plan d'action pré-création : spécification" (section 6).

Ce document couvre l'infrastructure roadmap (tables, seed), le service de suivi (statuts, cascade, preuves) et — nouveauté ajoutée par OPENCODE — le moteur de filtrage par profil et la condition n°21 (régime fiscal IS/IR), qui consomme la table `project_associates` (socle Groupe 5, voir plus bas).

---

## Décision préalable — filtrage à l'affichage, jamais à la sélection

Choix tranché avant l'implémentation : **tous les nœuds sont assignés dès le premier accès** (`statut` effectif ou `verrouille`), et le filtrage sur `roadmap_nodes.applicable_if` se fait **au moment de l'affichage** (`list_roadmap`), jamais à la création des `startup_roadmap_items`.

- Les statuts vivent donc sur la « totalité » du graphe : cocher une étape qui devient inapplicable plus tard continue de la masquer, mais sa progression reste stockée (pas de disparition silencieuse de l'historique).
- Le statut ne rentre pas en compte dans le filtrage : un nœud `en_cours`/`termine` devenu inapplicable est aussi masqué, conformément à la décision de cadrage.
- Conséquence machine : `_ensure_items` s'appuie sur la liste complète des nœuds en base, pas sur une sous-liste filtrée — aucun recyclage besoin quand les conditions changent.

---

## Infrastructure roadmap (Groupe 1, socle préexistant au travail OPENCODE)

### `backend/entrepreneur/models/roadmap_node.py` / `roadmap_node_dependency.py` / `startup_roadmap_item.py`

- `roadmap_nodes` : définition d'une étape (id, groupe, ordre, nom, input, description, details_pratiques, administration_liee, source_legale, bloquant) + `applicable_if` (JSON, condition par opérateur-→-opérande) + `node_snapshot` (copie figée du texte descriptif, pas des méta-données structurelles).
- `roadmap_node_dependencies` : arêtes du graphe (`depends_on`), source du déverrouillage en cascade.
- `startup_roadmap_items` : une ligne par (projet, nœud) avec `statut`, horodatages, et `proof_document_id` (FK vers `documents` pour la preuve d'une étape). Contrainte d'unicité `uq_startup_roadmap_items_project_node`.

### `backend/entrepreneur/scripts/seed_roadmap_nodes.py`

Charge les 24 nœuds depuis `scripts/data/wink_roadmap_creation_juridique.json` (5 groupes : `g0_decisions_prealables` → `g1_constitution_capital` → `g2_formalites_prealables` → `g3_immatriculation` → `g4_obligations_post`), **valide le graphe** (dépendances orphelines + cycles par DFS — le graphe est un DAG), puis upsert nœuds + dépendances. Idempotent.

### `backend/entrepreneur/scripts/data/wink_roadmap_creation_juridique.json`

Source unique des 24 nœuds. Trois nœuds portent une condition `applicable_if` :

| Nœud | Groupe | Opérateur | Seuil / valeur | Sens |
|---|---|---|---|---|
| `e4_pacte_fondateurs` | g0 | `nb_cofondateurs_gte` | 2 | pacte de fondateurs affiché seulement si ≥ 2 cofondateurs |
| `e21_immatriculation_fiscale` | g0 | `droits_de_vote_dirigeants_foyer_fiscal_gt` | 34 | option IS/IR affichée seulement si > 34 % des droits de vote détenus par les dirigeants + foyer fiscal (art. 239 bis AB du CGI) |
| `e23_depot_marque` | g4 | `objectifs_immediats_contains` | `protection_marque_code` | dépôt de marque affiché seulement si l'utilisateur a coché cet objectif à l'onboarding |

Tous les autres nœuds ont `applicable_if: {}` → toujours affichés.

---

## Service de suivi (cœur du 1.1.11, Groupe 1)

### `backend/entrepreneur/schemas/roadmap_schemas.py`

- `RoadmapItemRead` : item + `groupe`/`ordre` **lus en live depuis `roadmap_nodes`** (position/regroupement = méta-données structurelles, pas du contenu figé), `node_snapshot` (contenu figé), `depends_on` (prérequis directs uniquement — suffisant pour les flèches et la liste "Étapes requises" côté frontend), `proof_document_url` (rejoint via `Document.current_version_id`).
- `RoadmapItemUpdate` : `statut` restreint à `RoadmapItemSettableStatut` — **`verrouille` volontairement absent** : seul `_cascade_unlock` (côté serveur) peut le poser/le lever, jamais un client.

### `backend/entrepreneur/services/roadmap_service.py`

- **`_ensure_items(db, project_id)`** — peuplage au premier accès : crée les `startup_roadmap_items` manquants (tous les nœuds, sans filtre), puis pose `a_faire` sur les racines (satisfaites par le « vrai vide » de `_is_satisfied`) et commit. Course possible entre deux premiers accès simultanés (`uq_...`) : non gérée, même niveau de robustesse que le reste du service.
- **`_cascade_unlock` / `_dependents` / `_dependencies_map`** — propage récursivement le déverrouillage aux nœuds dont les prérequis viennent de passer à `termine`/`non_necessaire`. `_dependencies_map` est la version groupée (une seule requête) pour `list_roadmap` — évite le N+1 que `_dependencies` (appelée par nœud) aurait créé sur 24 nœuds.
- **`_base_item_query` / `_row_to_read` / `_read_item`** — requête unique avec jointures (`roadmap_nodes`, `documents`, `document_versions`) : un seul endroit à faire évoluer pour ajouter une colonne de lecture. La preuve utilise un `outerjoin` (un document sans version rattachée reste visible).
- **`update_status(db, user, project_id, node_id, statut)`** — cocher une étape `verrouille` est **autorisé** (cas réel : un entrepreneur qui a commencé ses démarches avant d'utiliser Wink — comportement n°1 de la spec, aucune condition de déblocage mentionnée). Passe `completed_at` et déclenche la cascade si le nouveau statut est satisfaisant.
- **`attach_proof(...)`** — dépôt d'une preuve par étape. MIME autorisés : **PDF, PNG, JPEG** (pas seulement PDF, contrairement à l'import d'onboarding — une photo de Kbis ou de statuts signés est un cas d'usage réel ; pas d'extraction derrière, donc pas la contrainte du pipeline VLM). Réutilise le mécanisme de `document_service.upload_and_extract` : nouvelle version si une preuve existe déjà, sinon premier upload. Upload via `cloudinary_service.upload_raw_file(folder="wink/roadmap-proofs")`.

### `backend/entrepreneur/routes/roadmap_router.py`

Trois routes, `_handle_roadmap_error` comme point unique de mapping (`ProjectNotFoundError`/`RoadmapItemNotFoundError` → 404, `ForbiddenError` → 403, reste → 400) :

- `GET /projects/{id}/roadmap` → `list_roadmap` (peuplement + **filtrage applicable_if** + tri par `ordre`).
- `PATCH /projects/{id}/roadmap/{node_id}` → `update_status`.
- `POST /projects/{id}/roadmap/{node_id}/proof` → `attach_proof` (201, upload multipart).

---

## Moteur de filtrage `applicable_if` (travail OPENCODE, 1.1.11)

### `_evaluate_applicable_if(applicable_if, project, db)`

`graphe vide = toujours applicable` ; sinon `all(...)` sur chaque `(opérateur, opérande)` — une condition ET entre opérateurs, chaque opérateur restant indépendant. Appliquée dans `list_roadmap` comme filtre sur les lignes **déjà triées par `ordre`** (ligne 293).

### `_apply_condition(operator, operand, project, db)`

**Sélecteur inverse** : tout opérateur inconnu à venir est évalué "toujours satisfait" — quand sa donnée existera, seul ce mapping évolue, pas l'architecture de filtrage. Opérateurs implémentés :

1. **`nb_cofondateurs_gte`** (`e4_pacte_fondateurs`) — lit `project.nombre_cofondateurs`. **Fail-open** si `None` : tant que l'onboarding n'a pas renseigné la donnée, on ne masque pas par défaut.
2. **`objectifs_immediats_contains`** (`e23_depot_marque`) — `operand in (project.objectifs_immediats or [])`. Liste vide = non satisfaite (c'est une donnée cochantée explicitement à l'onboarding, pas un champ qu'on « n'a pas encore rempli ») — l'inverse du fail-open de `nb_cofondateurs_gte`, car le sens de la condition est différent (obligation déclenchée par une case cochée).
3. **`droits_de_vote_dirigeants_foyer_fiscal_gt`** (`e21_immatriculation_fiscale`) — la condition la plus riche, voir section suivante.

---

## Condition e21 — régime fiscal IS/IR (art. 239 bis AB du CGI)

### Évolution du mode de calcul (décisions successives)

Le seed historique (`wink_roadmap_creation_juridique.json:380-382`) spécifiait bien l'opérateur `droits_de_vote_dirigeants_foyer_fiscal_gt` avec le seuil 34, mais **le mode de calcul n'était pas documenté** dans les fichiers de conception — seule subsistait la décision initiale « Option A : somme des dirigeants ». En travaillant la condition, un cas réel l'a mise en défaut : une société à 2 associés à 50/50 dont un seul est dirigeant cumule 50 %, ≥ au seuil actuel, mais ne remplirait **pas** la condition fiscale réelle — l'art. 239 bis AB exige en pratique que les dirigeants **et leur foyer fiscal** (conjoint/PACS/enfants à charge, art. 6 CGI) détiennent ensemble plus de 34 % des droits de vote.

**Décision validée (remplace l'Option A) : union dirigeants ∪ foyer fiscal** — un associé `est_dirigeant=true` est « chef de foyer », et chaque associé rattaché à un foyer (`foyer_fiscal_dirigeant_associate_id` non nul) compte dans le total.

### Implémentation (deux requêtes, union)

```python
votes = query(coalesce(pourcentage_droits_vote, pourcentage_capital))
        .filter(project_id == ..., est_dirigeant.is_(True)).all()          # dirigeants
foyer = query(coalesce(pourcentage_droits_vote, pourcentage_capital))
        .filter(project_id == ..., foyer_fiscal_dirigeant_associate_id.is_not(None),
                est_dirigeant.is_(False)).all()                           # rattachés au foyer
total = somme(votes) + somme(foyer) ; return total > operand
```

- **Droits de vote NULL = droits proportionnels au capital** (`coalesce`) — cohérent avec la lecture front de `TeamCapitalPage` (helper `droitsDeVote`).
- **Fail-open conservé** : pas une seule ligne dirigeante (donnée évidemment pas encore saisie) → la condition renvoie `True`, le nœud e21 reste affiché. Sans ça, e21 disparaîtrait tant que « Équipe & capital » est vide, et l'utilisateur ne saurait jamais pourquoi.
- **Contrôle en amont côté frontend** : l'indicateur « Dirigeants + foyer : XX % » de `TeamCapitalPage` affiche le même total et masque/affiche e21 explicitement (verdict `> 34 : régime IR (e21) accessible` / `≤ 34 : étape e21 masquée`).

---

## Dépendance transversale — socle `project_associates` (Groupe 5)

La condition e21 consomme une table du Groupe 5 (« Équipe & capital »), dont la migration socle a été **écrite en amont pour servir 1.1.11** (avant même l'écran associés) :

### `backend/alembic/versions/e1b2c3d4e5f6_*` (socle Groupe 5)

Crée `project_legal_profiles` **et** `project_associates` (nom, type (`fondateur`/`investisseur`/`salarie`/`autre`), `est_dirigeant`, `pourcentage_capital`, `pourcentage_droits_vote` nullable, FK projet). C'est la table que lit l'opérateur e21.

### `backend/alembic/versions/f7b1c2d3e4f6_add_foyer_fiscal_dirigeant_associate_id.py` (tête `alembic current`)

Ajoute `project_associates.foyer_fiscal_dirigeant_associate_id` (FK auto-référente `ondelete='SET NULL'`, nullable) pour modéliser le rattachement au foyer fiscal du dirigeant (décision d'extension, voir recap Équipe & capital). **C'est cette colonne que l'opérateur e21 teste** via `is_not(None)`.

### Validation de la donnée côté « Équipe & capital »

`associate_service.py` (`_validate_foyer_target` / `_validate_dirigeant_not_in_foyer`) garantit : cible dirigeante du même projet, un dirigeant ne peut pas être rattaché à un foyer, et le rattachement est effacé si l'associé devient dirigeant. La cohérence e21 repose donc sur des données validées à l'écriture.

---

## Frontend

### `frontend/src/entrepreneur/api/roadmapApi.ts`

Client HTTP : `getRoadmap`, `updateRoadmapItemStatut`, `uploadRoadmapProof` (FormData). Types `RoadmapItemRead`/`RoadmapItemSettableStatut` alignés sur le backend.

### `frontend/src/entrepreneur/pages/PlanActionPage.tsx`

Page racine, nav de premier niveau (hors sous-arbre "Mon projet"). **Condition d'affichage** : `project.project_type === "not_created"` — vérifiée par son propre `GET /projects/me` (pas via `MyProjectLayout`). Trois modes de vue (`RoadmapViewToggle`) : Graphe / Sentier vertical (cartes de phase repliables, `GroupeNodes`) et Parcours (chemin vertical continu sans accordéon, `RoadmapPathView`). Popup de détail unique (`StepDetailPopup`) porte les actions (marquer fait, déposer une preuve) — plus d'actions inline. Rechargement complet de la liste après chaque action (la réponse d'un toggle ne renvoie que l'item modifié, mais la cascade peut changer d'autres statuts — recharger est plus sûr que patcher localement). Intègre par ailleurs l'historique du service 1.1.2 (vérification de nom) chargé en parallèle.

### `frontend/src/entrepreneur/components/roadmap/roadmapLayout.ts`

Fichier pur (aucune dépendance React/DOM), testable hors rendu. Deux algorithmes, partageant `layerRows` (couche = 1 + couche max des dépendances internes au groupe ; nœud sans dépendance interne = couche 0 ; ordre stable par `ordre`) :

- **`computeGroupLayout(items, viewMode)`** — grille d'UN groupe, consommée par `RoadmapGraphCanvas` (Graphe = colonnes horizontales, Sentier = lignes verticales). Les dépendances vers un autre groupe ne sont jamais dessinées (traversent une frontière de carte de phase) — détail gardé dans le popup ("Étapes requises").
- **`computeFullPathLayout(items)`** — toute la roadmap en chemin vertical continu, groupée par section avec étiquette entre sections, largeur de carte adaptée au nombre de branches (`pathBranchGeometry`, dans l'esprit du mockup de référence). Même règle que la grille pour les dépendances inter-sections.

### `frontend/src/entrepreneur/components/roadmap/StepNode.tsx` / `PathStepCard.tsx` / `GroupeNodes.tsx` / `RoadmapPathView.tsx` / `RoadmapViewToggle.tsx`

Rendu SVG des nœuds et flèches (graphe/sentier), cartes du parcours (avec statut en badge et libellé "Non applicable" côté parcours), accordéons de phase, bascule de vue. Icônes SVG inline (`strokeWidth={2}`), palette de l'app (indigo/ambre), aucune librairie ajoutée.

### `frontend/src/entrepreneur/components/roadmap/StepDetailPopup.tsx`

Popup de détail commun aux trois vues (marquer fait, déposer une preuve, bouton 1.1.2 pour la disponibilité du nom). Points créés par OPENCODE :

- **Verdict 1.1.2** (déjà en place) : verdict synthétique Nom/Marque recalculé côté client depuis une règle fixe (priorité au Nom, la Marque ne nuance qu'un Nom déjà libre).
- **Bannière "Données utilisées"** (`TEAM_CAPITAL_DATA_NODES` = `e4_pacte_fondateurs`, `e5_redaction_statuts`, `e11_dbe`, `e21_immatriculation_fiscale`) : pour ces 4 nœuds dont la donnée source vit dans « Équipe & capital » (`project_associates`), un encart invite l'utilisateur à gérer les associés (lien vers la page) — oriente vers le socle partagé Groupe 5 (services 1.1.13 pacte / 1.1.4 statuts / 1.1.6 DBE / condition e21).

---

## Vérification

- Backend : `py_compile` OK ; `from backend.main import app` = `APP_IMPORT_OK`.
- `alembic upgrade head` appliqué, `alembic current` = `f7b1c2d3e4f6 (head)`.
- Frontend : `npx tsc -b` = seulement 4 erreurs préexistantes hors périmètre (`ResearcherProfileDetailsPage.tsx:249` TS6133 ; `ProjectPublicProfilePage.tsx:55,59,61` TS2345) ; `npm run lint` = 0 erreur, 9 warnings préexistants.
- E2E (`associate_e2e.py`, script jetable dans Temp, hors repo) : 17 scénarios, dont la page « Équipe & capital » complète (PUT global, foyer fiscal, fondateur). Les scénarios e21 s'appuient sur le même socle d'associés pour vérifier la condition `> 34`. SAWarning bénin en cleanup (`DELETE ... 0 matched`, cascade).

## Points à revisiter / dette

- **Opérateurs du moteur applicatif sans test unitaire automatisé dans le repo** : le moteur `_apply_condition` est vérifié par les E2E jetables, pas par un test PyTest versionné — couverture à ajouter côté backend si le projet en gagne.
- **`statut` sans `CheckConstraint`** (dette Groupe 1 préexistante) : les valeurs restent listées du côté Pydantic uniquement.
- **Contracture collecte vs condition** : `nb_cofondateurs_gte` est faill-open à `None`, `objectifs_immediats_contains` non — c'est un choix par sens de condition (champ à remplir vs case à cocher), à documenter explicitement pour les futurs opérateurs.
- **Course de premier accès** dans `_ensure_items` (deux requêtes concurrentes sur un projet vierge) : non gérée, assumée.
- **V2/V3 du service (copilot, lancement direct de service)** : hors périmètre V1, voir spec section 6.