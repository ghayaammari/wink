# Plan d'implémentation — Groupe 4 (services indépendants du copilot)

Ce document fixe ce qui a été décidé pour le Groupe 4 : quels services le composent, quelles tables chacun nécessite, dans quel ordre on les implémente, et les points laissés ouverts. Source : conversation Notion "Historique complet — Groupe 4 et discussion vérification légale" + "Récapitulatif — Décisions Entrepreneur (Groupe 4 + vérification légale)" (2026-09-12), et l'implémentation réelle menée en session.

---

## 1. Pourquoi ce groupement

Groupe 4 = les services d'EPIC-01 qui ne dépendent d'aucun agent IA/copilot — recherche croisée sur API publiques, vue de consultation, job périodique. Choisis ensemble parce qu'ils partagent cette propriété, pas parce qu'ils sont fonctionnellement liés entre eux.

## 2. Les 4 services — verdict table par table

| Service | Besoin réel | Table(s) | Statut |
|---|---|---|---|
| **1.1.2 — Vérificateur de disponibilité du nom** | Stocker l'historique des noms testés (plusieurs vérifications possibles par projet), pas juste un statut de progression | `name_availability_checks` (nouvelle) | ✅ Implémenté |
| **1.1.17 — Coffre-fort documentaire** | Vue centralisée des documents du projet, filtrable par type/service d'origine — aucune donnée propre, le "service d'origine" se déduit de `document_type` | Aucune — vue sur `documents`/`document_versions` (I0) existantes | À implémenter (prochain) |
| **1.1.9 — Notification de disponibilité du Kbis** | Un changement de statut seul ne "notifie" pas — il faut un objet métier visible + un lien vers l'action suivante | `notifications` (nouvelle, générique — réutilisable pour toute notification future) | À implémenter |
| **Nouveau — Vérification SIREN/SIRET** (à numéroter, ex. 1.1.18) | Validation Luhn immédiate (frontend) + confirmation d'existence réelle via API après soumission | Aucune — écrit directement dans `project_legal_profiles` | À implémenter |

**Verdict tables Groupe 4** : 2 nouvelles tables (`name_availability_checks`, `notifications`) + 5 nouveaux attributs sur `project_legal_profiles` existante. Aucune autre table.

## 3. Ordre d'implémentation décidé

1. **1.1.2 — Vérificateur de disponibilité du nom** ✅ terminé (voir détail section 5).
2. **1.1.17 — Coffre-fort documentaire** — prochain service, aucune nouvelle table, scope confirmé section 6.
3. **1.1.9 — Notification Kbis** — job périodique + table `notifications`.
4. **Nouveau service SIREN/SIRET** — à numéroter formellement.
5. **Parcours A / Parcours B** (section 7) — pas un service à part, mais le cadre qui détermine comment/quand `project_legal_profiles` se remplit pour 1.1.9 et la vérification SIREN/SIRET ; à implémenter en cohérence avec ces deux services plutôt qu'après coup.

---

## 4. Clarification structurante — Kbis = document, pas un numéro

| Élément | Nature | Où il vit |
|---|---|---|
| SIREN, SIRET | Numéros | `project_legal_profiles` |
| Code APE = Code NAF | Un seul et même code | `project_legal_profiles.naf_code` |
| RNE | Un registre (pas un identifiant, pas un document) | Nulle part à stocker |
| Kbis | **Fichier PDF**, carte d'identité de la société | `documents` / `document_versions`, `document_type = 'kbis'` |

**Limite structurante** : Wink n'a aucun moyen automatisé et gratuit de télécharger le Kbis à la place de l'utilisateur (MonIdenum réservé au représentant légal authentifié, Infogreffe payant). `kbis_document_id` reste `NULL` tant que l'utilisateur ne l'uploade pas lui-même. Le service 1.1.9 se limite à détecter que le Kbis **existe** (`etat_administratif = actif` via l'API Recherche d'Entreprises), jamais à le récupérer.

---

## 5. Service 1.1.2 — Vérificateur de disponibilité du nom (implémenté)

Recherche croisée sur deux API publiques :
- **Recherche d'Entreprises** (`scrapers/recherche_entreprises/client.py`) — dénomination sociale, sans authentification.
- **Base Marques INPI** (`scrapers/inpi/marques_client.py`) — dépôt de marque, authentification par compte personnel (`INPI_USERNAME`/`INPI_PASSWORD`).

Table `name_availability_checks` : historique append-only, un enregistrement par vérification (`nom_teste`, `statut_denomination`, `statut_marque`, `verifie_le`), aucune contrainte d'unicité — un même nom peut être re-testé.

**Points vérifiés en test réel (2026-09-12)** sur l'API INPI, documentés en détail dans `marques_client.py` :
- Authentification en 3 étapes (CSRF via cookie `XSRF-TOKEN`, puis login avec le token en header ET cookie, puis le header repassé à chaque appel authentifié suivant).
- Requête de recherche par **phrase exacte obligatoire** (`[Mark="<nom>"]`, guillemets requis) — sans guillemets, recherche plein texte large donnant de faux négatifs (`disponible` alors que la marque existe).
- Réponse en JSON via `Accept: application/json` explicite (le `Content-Type` retourné par le serveur est trompeur).

**UI** : historique affiché dans `StepDetailPopup.tsx` sous forme de verdict synthétisé (badge rouge/orange/vert + libellé + sous-texte), calculé côté client depuis une règle métier fixe (`verdictCombinaison`), avec le détail Nom/Marque gardé en badges secondaires — décision validée par mockup Artifact avant implémentation.

**Point produit resté ouvert** : le statut INPI "Demande publiée" (dépôt en cours, pas encore enregistré) n'est actuellement pas traité comme bloquant. À trancher si une demande en cours doit compter comme "risque".

---

## 6. Service 1.1.17 — Coffre-fort documentaire (prochain)

Vue de consultation centralisée de tous les documents liés au projet, filtrable par type ou service d'origine. Réutilise `documents`/`document_versions` (I0), aucune nouvelle table.

| Colonne existante (`documents`) | Rôle pour le coffre-fort |
|---|---|
| `project_id` | Filtrer tous les documents d'un projet |
| `document_type` | Filtrer par type (statuts, pacte, Kbis...) — déduit le "service d'origine" sans champ dédié |
| `owner_user_id` | Savoir qui a uploadé/généré le document |
| `current_version_id` → `document_versions` | Accéder au fichier réel via Cloudinary |

**Limite réelle identifiée en session** : `documents.document_type` a aujourd'hui un `CHECK` qui n'autorise que `'entrepreneur_idea'` / `'other'` (I0). Les valeurs supposées par ce service (`'statuts'`, `'kbis'`, `'pacte'`...) n'existent pas encore — elles seront ajoutées une à une par les services qui les produiront (1.1.4, 1.1.9...), pas par 1.1.17 lui-même. Le coffre-fort fonctionnera dès son implémentation mais n'affichera que les documents I0 tant que ces services ne sont pas livrés.

**Plan d'implémentation retenu** (fichier séparé de `document_router.py`, scopé au service 0.0.2 — une responsabilité par fichier) :
- `document_vault_schemas.py` — réponse enrichie document + dernière version.
- `document_vault_service.py` — liste les documents d'un projet appartenant à l'utilisateur.
- `document_vault_router.py` — `GET /projects/{id}/documents`.
- Frontend : 4e carte sur `MyProjectPage.tsx` → `DocumentVaultPage.tsx` sous `MyProjectLayout` existant.

---

## 7. Parcours A vs Parcours B — remplissage de `project_legal_profiles`

Le rythme de remplissage diffère selon si la startup existe déjà ou non.

### Parcours A — `project_type = not_created` (collecte étalée en 4 vagues)

| Vague | Champs | Débloqué à quel nœud | Mode de remplissage |
|---|---|---|---|
| 1 | `legal_form` | `e1` | Saisie humaine |
| 1 | `registered_address` | `e6` | Saisie humaine |
| 1 | `legal_name`, `legal_representative` | `e5` | Saisie humaine |
| 2 | `siren`, `siret`, `naf_code` | `e16` | Automatique — API Guichet Unique interrogée avec `numero_suivi_formalite` (obtenu à `e13`) |
| 3 | statuts de vérification, `registration_date` | `e17` | Automatique — job périodique sur API Recherche d'Entreprises |
| 4 | `kbis_document_id` | Dès upload | Manuel, utilisateur |

### Parcours B — `project_type = created` (collecte groupée)

Tout saisi en une fois à l'Écran 3 (sauf Kbis). Un seul appel API (`recherche-entreprises.api.gouv.fr?q=siren:X&with_etat_administratif=true`) confirme simultanément `immatriculation_verification_status` et `kbis_verification_status`. `denomination_verification_status` se déduit par comparaison texte (nom saisi vs dénomination retournée par l'API).

**Conséquence UI actée** : la section "Informations légales" de Mon Projet doit afficher 3 états visuels distincts par champ — *à remplir* / *verrouillé* / *en attente de vérification automatique*.

### Les 3 statuts de vérification séparés — principe retenu

| Colonne | Vérifie | Source |
|---|---|---|
| `denomination_verification_status` | `legal_name` | Comparaison texte vs API |
| `immatriculation_verification_status` | `siren`, `siret`, `naf_code`, `vat_number` | Un seul appel API (même instant, même source) |
| `kbis_verification_status` | Existence/activité réelle de l'entreprise | API Recherche d'Entreprises |

**Principe réutilisable ailleurs dans le projet** : le niveau de granularité d'un statut de vérification suit le niveau de granularité de **l'événement qui produit la donnée**, pas le nombre de colonnes concernées — SIREN/SIRET/NAF/TVA partagent un seul statut (même appel API), dénomination et Kbis en ont chacun un séparé (sources différentes).

`is_registered` et `verification_status` (uniques, existants) sont **retirés**, remplacés par ces 3 statuts.

---

## 8. Schéma décidé — 5 nouveaux attributs sur `project_legal_profiles`

| Attribut ajouté | Type | Règles | Utilisé quand |
|---|---|---|---|
| `kbis_document_id` | UUID | FK → `documents.id`, NULL | Affiché dans Mon Projet une fois `kbis_verification_status = verifie` |
| `denomination_verification_status` | VARCHAR | NOT NULL, défaut `non_verifie` | Badge vert/orange sur la section légale |
| `immatriculation_verification_status` | VARCHAR | NOT NULL, défaut `non_verifie` | Débloque l'affichage fiable SIREN/SIRET/NAF |
| `kbis_verification_status` | VARCHAR | NOT NULL, défaut `non_verifie` | Déclenche la notification finale + débloque `e17` |
| `numero_suivi_formalite` | VARCHAR | NULL | Clé d'interrogation Guichet Unique, rempli à `e13`, utilisé jusqu'à `e16`, jamais affiché |

Valeurs possibles pour chaque statut : `non_verifie` / `verifie` / `incoherent`.

⚠️ **Écart à consolider avant de figer ce schéma** : un document PDF fourni séparément (Groupe 5, section modification `project_legal_profiles` — I0) liste des changements différents sur la même table (`legal_representative` remplacé par `legal_representative_associate_id`, ajout de `objet_social`/`duree_societe`/`date_signature_statuts`). Ce sont deux évolutions distinctes de la même table (Groupe 4/vérification vs Groupe 5/statuts) — à consolider en un seul schéma final avant migration, sinon risque d'écraser l'une des deux séries de changements.

---

## 9. Points ouverts, jamais tranchés

- **Accès API Guichet Unique / e-procedures INPI** pour interroger `numero_suivi_formalite` — nécessite un compte développeur, accès libre ou soumis à habilitation non confirmé. Bloquant réel pour la Vague 2 du Parcours A : si l'accès s'avère restreint, prévoir un repli (saisie manuelle du SIREN dès qu'il est connu, sans job automatique). **Prochaine étape logique avant de considérer le Groupe 4 comme clos.**
- **Statut INPI "Demande publiée"** (1.1.2) — compter ou non comme "risque" dans `verdictCombinaison`. Non tranché.
- **`documents.document_type` CHECK constraint** (1.1.17) — à étendre au fur et à mesure que 1.1.4, 1.1.9 etc. produisent leurs propres documents. Pas un blocage pour 1.1.17 lui-même.
- **Écart de schéma `project_legal_profiles`** entre Groupe 4 et Groupe 5 (section 8) — à consolider avant migration.
