# Wink — Schéma de données pour I0 (Identité & Onboarding) — Entrepreneur

Ce document décrit les tables réellement créées en base pour l'Incrément 0 : les 3 tables partagées (identité/auth, communes aux 3 rôles) et les 7 tables du domaine Entrepreneur. Généré à partir des modèles SQLAlchemy sous `backend/shared/models/` et `backend/entrepreneur/models/`.

Convention commune à toutes les tables : `id` en `UUID`, généré côté base par `gen_random_uuid()` (`server_default`). Les tables métier (hors tokens) ont `created_at` / `updated_at` en `timestamptz`, remplis automatiquement (`server_default=func.now()`, `onupdate=func.now()` pour `updated_at`).

---

## 1. `users`

Compte applicatif, commun aux 3 rôles. Une ligne par personne inscrite, quel que soit son rôle.

| Champ | Type | Contraintes | Valeurs possibles / remarque |
|---|---|---|---|
| `id` | UUID | PK | généré par la base |
| `email` | varchar(320) | `UNIQUE`, `NOT NULL` | + index unique séparé sur `lower(email)` : deux emails qui ne diffèrent que par la casse sont considérés identiques |
| `first_name` | varchar(120) | nullable | |
| `last_name` | varchar(120) | nullable | |
| `password_hash` | varchar(255) | nullable | `NULL` si connexion Google uniquement |
| `auth_provider` | varchar(20) | `NOT NULL`, défaut `'email'`, `CHECK` | `'email'` \| `'google'` |
| `provider_subject` | varchar(255) | `UNIQUE`, nullable | `sub` du token Google ; `NULL` si compte email |
| `role` | varchar(20) | `NOT NULL`, `CHECK` | `'entrepreneur'` \| `'chercheur'` \| `'investisseur'` — fixé à l'inscription, non modifiable ensuite |
| `created_at` | timestamptz | `NOT NULL`, auto | |
| `updated_at` | timestamptz | `NOT NULL`, auto | |

**Contraintes `CHECK` inter-champs (cohérence auth) :**
- `auth_provider <> 'email' OR password_hash IS NOT NULL` — un compte email doit avoir un mot de passe.
- `auth_provider <> 'google' OR provider_subject IS NOT NULL` — un compte Google doit avoir son identifiant Google.

Ces deux règles empêchent en base un état incohérent (ex. compte "email" sans mot de passe) que le code applicatif pourrait laisser passer par erreur.

**Relations :** table racine — toutes les autres tables ci-dessous en dépendent, directement ou via une table de liaison (`entrepreneur_profiles`).

---

## 2. `refresh_tokens`

Sessions de rafraîchissement JWT, révocables individuellement.

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | `NOT NULL`, FK → `users.id` (`ON DELETE CASCADE`), indexé | |
| `token_hash` | varchar(64) | `UNIQUE`, `NOT NULL` | SHA-256 du token, jamais le token en clair |
| `expires_at` | timestamptz | `NOT NULL` | |
| `revoked_at` | timestamptz | nullable | `NULL` = encore valide ; posé à la rotation ou au logout |
| `created_at` | timestamptz | `NOT NULL`, auto | |

**Relation :** N `refresh_tokens` → 1 `users` (un utilisateur peut avoir plusieurs sessions actives, ex. plusieurs appareils).

---

## 3. `password_reset_tokens`

Jetons de réinitialisation de mot de passe, usage unique.

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | `NOT NULL`, FK → `users.id` (`ON DELETE CASCADE`), indexé | |
| `token_hash` | varchar(64) | `UNIQUE`, `NOT NULL` | SHA-256, jamais en clair |
| `expires_at` | timestamptz | `NOT NULL` | durée courte (config `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`, 60 min par défaut) |
| `used_at` | timestamptz | nullable | `NULL` = encore utilisable ; posé à l'usage |
| `created_at` | timestamptz | `NOT NULL`, auto | |

**Relation :** N `password_reset_tokens` → 1 `users`.

---

## 4. `entrepreneur_profiles`

Table fine de liaison `users` ↔ rôle entrepreneur. Ne porte aucun champ métier — tout le déclaratif vit dans `projects`. Prépare la possibilité qu'un entrepreneur porte plusieurs projets un jour, sans changer la structure.

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | `UNIQUE`, `NOT NULL`, FK → `users.id` (`ON DELETE CASCADE`) | 1-1 avec `users` |
| `created_at` / `updated_at` | timestamptz | `NOT NULL`, auto | |

**Relation :** 1-1 avec `users` (`UNIQUE` sur `user_id`) ; 1-N vers `projects`.

---

## 5. `projects`

L'idée ou la startup présentée par l'entrepreneur. Table centrale du domaine.

| Champ | Type | Contraintes | Valeurs possibles / remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `entrepreneur_profile_id` | UUID | `NOT NULL`, FK → `entrepreneur_profiles.id` (`ON DELETE CASCADE`) | |
| `project_type` | varchar(20) | `NOT NULL`, `CHECK` | `'not_created'` \| `'created'` |
| `stage` | varchar(20) | `NOT NULL`, `CHECK` | `'ideation'` \| `'pre_seed'` \| `'seed'` \| `'serie_a'` |
| `description` | text | nullable | répondu à l'écran 4 du questionnaire — le projet existe déjà (créé à l'écran 2) sans ce champ : état transitoire normal |
| `source_type` | varchar(20) | nullable, `CHECK` | `'texte_libre'` \| `'document_importe'` ; `NULL` tant que l'écran 4 n'est pas passé |
| `imported_document_id` | UUID | nullable, FK → `documents.id` | FK circulaire avec `documents` (voir plus bas), ajoutée par `ALTER TABLE` (`use_alter=True`) |
| `nombre_cofondateurs` | integer | nullable | |
| `intention_levee_fonds` | boolean | nullable | |
| `localisation` | varchar(120) | nullable | |
| `sector` | varchar(120) | nullable | |
| `subsectors` | jsonb | `NOT NULL`, défaut `'[]'` | liste |
| `customer_segments` | jsonb | `NOT NULL`, défaut `'[]'` | liste |
| `target_users` | jsonb | `NOT NULL`, défaut `'[]'` | liste |
| `technologies` | jsonb | `NOT NULL`, défaut `'[]'` | liste |
| `value_proposition` | text | nullable | |
| `project_profile_completion` | varchar(20) | `NOT NULL`, défaut `'incomplet'`, `CHECK` | `'incomplet'` \| `'complet'` |
| `created_at` / `updated_at` | timestamptz | `NOT NULL`, auto | |

**Contrainte `CHECK` inter-champs :**
- `source_type <> 'document_importe' OR imported_document_id IS NOT NULL` — si la source est un document importé, le document doit être renseigné.

**Relations :**
- N `projects` → 1 `entrepreneur_profiles`.
- 1 `projects` → 0..1 `documents` (import qui a servi à créer le projet, via `imported_document_id`).
- 1 `projects` → N `documents` (tous les documents liés au projet, via `documents.project_id`).
- 1 `projects` → 0..1 `project_legal_profiles` (1-1).
- 1 `projects` → 0..1 `project_public_profiles` (1-1).
- 1 `projects` → N `project_field_values`.

---

## 6. `project_legal_profiles`

Identité légale du projet (pour les startups déjà immatriculées).

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `project_id` | UUID | `UNIQUE`, `NOT NULL`, FK → `projects.id` (`ON DELETE CASCADE`) | 1-1 avec `projects` |
| `is_registered` | boolean | `NOT NULL`, défaut `false` | |
| `legal_name` | varchar(255) | nullable | |
| `legal_form` | varchar(120) | nullable | ex. SAS, SARL — pas de `CHECK` de valeurs en base actuellement |
| `registration_number` | varchar(120) | nullable | |
| `siren` | varchar(9) | nullable, indexé | |
| `siret` | varchar(14) | nullable, indexé | |
| `vat_number` | varchar(40) | nullable | |
| `naf_code` | varchar(10) | nullable | |
| `registration_date` | date | nullable | |
| `registered_address` | jsonb | nullable | objet libre |
| `legal_representative` | jsonb | nullable | objet libre |
| `verification_status` | varchar(30) | `NOT NULL`, défaut `'unverified'` | pas de `CHECK` de valeurs en base actuellement |
| `created_at` / `updated_at` | timestamptz | `NOT NULL`, auto | |

**Relation :** 1-1 avec `projects` (`UNIQUE` sur `project_id`).

> Remarque maintenabilité : contrairement à `documents`, `projects` et `project_field_values`, cette table n'a pas de `CheckConstraint` sur `verification_status` ni `legal_form` — rien n'empêche aujourd'hui une valeur incohérente d'être insérée hors du chemin applicatif normal. À trancher consciemment si une source externe (import INPI, admin direct en base) doit un jour écrire dans cette table.

---

## 7. `project_public_profiles`

Vitrine publique du projet (affichage externe, ex. matching investisseur).

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `project_id` | UUID | `UNIQUE`, `NOT NULL`, FK → `projects.id` (`ON DELETE CASCADE`) | 1-1 avec `projects` |
| `public_name` | varchar(255) | nullable | |
| `public_summary` | text | nullable | |
| `sector` | varchar(120) | nullable | dupliqué depuis `projects.sector` — vitrine indépendante, peut diverger volontairement |
| `technologies` | jsonb | `NOT NULL`, défaut `'[]'` | liste |
| `website_url` | text | nullable | |
| `logo_url` | text | nullable | URL Cloudinary directe, pas de FK vers `documents`/`document_versions` |
| `funding_visibility` | varchar(30) | `NOT NULL`, défaut `'private'` | pas de `CHECK` de valeurs en base actuellement |
| `compliance_visibility` | varchar(30) | `NOT NULL`, défaut `'private'` | pas de `CHECK` de valeurs en base actuellement |
| `published_at` | timestamptz | nullable | `NULL` = jamais publié |
| `updated_at` | timestamptz | `NOT NULL`, auto | (pas de `created_at` sur cette table) |

**Relation :** 1-1 avec `projects` (`UNIQUE` sur `project_id`).

---

## 8. `project_field_values`

Traçabilité de chaque champ extrait automatiquement d'un document, avec son statut de confirmation par l'utilisateur.

| Champ | Type | Contraintes | Valeurs possibles / remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `project_id` | UUID | `NOT NULL`, FK → `projects.id` (`ON DELETE CASCADE`) | |
| `field_name` | varchar(100) | `NOT NULL` | nom du champ cible (ex. `sector`, `legal_form`) |
| `field_value` | text | nullable | valeur brute extraite (ou saisie), toujours en texte |
| `extraction_source` | varchar(20) | `NOT NULL`, `CHECK` | `'extrait_automatique'` \| `'saisi_par_utilisateur'` |
| `validation_status` | varchar(30) | `NOT NULL`, défaut `'en_attente'`, `CHECK` | `'en_attente'` \| `'confirme'` \| `'corrige'` |
| `created_at` / `updated_at` | timestamptz | `NOT NULL`, auto | |

**Contrainte `UNIQUE` :** `(project_id, field_name)` — un seul enregistrement en attente par champ et par projet ; résoudre le champ (confirmer/corriger) écrit dans la vraie colonne de `projects`/`project_legal_profiles`/`project_public_profiles` puis supprime cette ligne (voir `ignore_field_value` / `resolve_field_value` côté service).

**Relation :** N `project_field_values` → 1 `projects`.

---

## 9. `documents`

Métadonnées de suivi d'un fichier importé. Le binaire reste sur Cloudinary ; le contenu réel (URL, taille, texte extrait) est dans `document_versions`.

| Champ | Type | Contraintes | Valeurs possibles / remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `owner_user_id` | UUID | `NOT NULL`, FK → `users.id`, indexé | pas de `ON DELETE CASCADE` (contrairement aux tokens) |
| `project_id` | UUID | nullable, FK → `projects.id` (`ON DELETE CASCADE`), indexé | `NULL` possible (document pas encore rattaché à un projet) |
| `document_type` | varchar(40) | `NOT NULL`, `CHECK` | `'entrepreneur_idea'` \| `'other'` |
| `visibility` | varchar(30) | `NOT NULL`, défaut `'private'`, `CHECK` | `'private'` \| `'project_members'` |
| `processing_status` | varchar(30) | `NOT NULL`, défaut `'uploaded'`, `CHECK` | `'uploaded'` \| `'queued'` \| `'processing'` \| `'ready'` \| `'failed'` |
| `current_version_id` | UUID | nullable, FK → `document_versions.id` | FK circulaire (voir ci-dessous) |
| `created_at` / `updated_at` | timestamptz | `NOT NULL`, auto | |

**FK circulaire `documents` ↔ `document_versions` :** `documents.current_version_id` → `document_versions.id` **et** `document_versions.document_id` → `documents.id`. Les deux tables se référencent mutuellement ; SQLAlchemy crée les deux tables d'abord puis ajoute `fk_documents_current_version_id` par `ALTER TABLE` (`use_alter=True`) pour casser la dépendance circulaire à la création.

**Relations :**
- N `documents` → 1 `users` (propriétaire).
- N `documents` → 0..1 `projects`.
- 1 `documents` → N `document_versions` (historique des uploads/ré-uploads).
- 1 `documents` → 0..1 `document_versions` (version courante, via `current_version_id`).

---

## 10. `document_versions`

Version immuable d'un fichier — chaque ré-upload crée une nouvelle ligne, jamais d'écrasement.

| Champ | Type | Contraintes | Remarque |
|---|---|---|---|
| `id` | UUID | PK | |
| `document_id` | UUID | `NOT NULL`, FK → `documents.id` (`ON DELETE CASCADE`) | |
| `version_number` | integer | `NOT NULL` | 1, 2, 3... incrémenté à chaque ré-upload |
| `original_filename` | varchar(500) | `NOT NULL` | |
| `cloudinary_public_id` | varchar(500) | `UNIQUE`, `NOT NULL` | identifiant interne Cloudinary |
| `secure_url` | text | `NOT NULL` | URL directe, utilisable si document public |
| `mime_type` | varchar(150) | `NOT NULL` | |
| `size_bytes` | bigint | `NOT NULL` | |
| `extracted_text_location` | text | nullable | texte brut extrait par le VLM, avant répartition dans `project_field_values` |
| `created_at` | timestamptz | `NOT NULL`, auto | (pas de `updated_at` — une version est immuable) |

**Contrainte `UNIQUE` :** `(document_id, version_number)` — pas deux fois le même numéro de version pour un même document.

**Relation :** N `document_versions` → 1 `documents`.

---

## Schéma relationnel — vue d'ensemble

```
users (1) ──< (N) refresh_tokens
users (1) ──< (N) password_reset_tokens
users (1) ──(1:1)── entrepreneur_profiles
users (1) ──(1:1)── researcher_profiles      (hors périmètre Entrepreneur, même pattern)
users (1) ──(1:1)── investor_profiles        (hors périmètre Entrepreneur, même pattern)

entrepreneur_profiles (1) ──< (N) projects

projects (1) ──(1:1)── project_legal_profiles
projects (1) ──(1:1)── project_public_profiles
projects (1) ──< (N) project_field_values
projects (1) ──< (N) documents                (documents.project_id)
projects (1) ──(0:1)── documents              (projects.imported_document_id — FK circulaire)

documents (1) ──< (N) document_versions
documents (1) ──(0:1)── document_versions     (documents.current_version_id — FK circulaire)

users (1) ──< (N) documents                   (documents.owner_user_id)
```

**Deux FK circulaires à connaître** (nécessitent `use_alter=True` côté SQLAlchemy, donc un `ALTER TABLE` après création des deux tables concernées) :
1. `documents.current_version_id` ↔ `document_versions.document_id`
2. `projects.imported_document_id` ↔ `documents.project_id`

---

## Hors périmètre de ce document

`researcher_profiles` et `investor_profiles` existent en base (même pattern que `entrepreneur_profiles` : liaison 1-1 avec `users`, aucun champ métier) mais n'ont pas de champs propres à ce stade — à enrichir par les équipes Chercheur/Investisseur. `backend/matching/` et `scrapers/` restent vides jusqu'aux incréments concernés (I5/I6 et I1).
