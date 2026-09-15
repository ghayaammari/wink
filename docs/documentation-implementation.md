# Documentation de l'implémentation — Wink

Journal cumulatif de tout ce qui a été **réellement implémenté**, organisé par Incrément → Groupe → Service. Mis à jour à chaque fois qu'un service ou une implémentation est terminé — ne jamais retirer une entrée existante, seulement en ajouter/mettre à jour le statut.

Chaque entrée renvoie, quand il existe, vers le récapitulatif détaillé du service (fichier par fichier, fonction par fonction) dans `docs/recap-service-*.md`. Ce document-ci reste au niveau choix + pourquoi + état, pas le détail d'implémentation ligne à ligne.

Pour le plan des services **pas encore implémentés** (prochaines étapes, ordre décidé), voir `docs/plan-implementation-groupe4.md` (et équivalents futurs par groupe) — ce fichier-ci ne documente que ce qui est fait.

---

## Incrément 0 — Identité & Onboarding (EPIC-00, volet Entrepreneur)

**Statut global : fonctionnellement complet sur le parcours principal.**

### 0.0.1 — Création de compte

**Statut :** Complet.

Inscription/connexion par email+mot de passe (bcrypt) ou Google OAuth (vérification `id_token` côté serveur), rôle choisi une seule fois à l'écran 1 et jamais redemandé. Session par access token JWT (30 min) + refresh token opaque haché SHA-256 avec rotation à usage unique. Mot de passe oublié avec réponse anti-énumération (même HTTP quelle que soit l'existence du compte) et lien à usage unique (60 min).

**Choix clés :**
- Table `users` unique pour les 3 rôles (entrepreneur/chercheur/investisseur) plutôt que 3 tables séparées — un seul modèle d'auth à maintenir, contraintes `CHECK` en base pour empêcher un compte email sans mot de passe ou un compte Google sans `provider_subject`.
- Refresh token opaque (pas un JWT) haché en base : un JWT refresh volé serait invérifiable côté serveur avant expiration ; l'opaque haché permet la révocation immédiate.

**Dette technique assumée :** tokens en `localStorage` (vulnérable XSS, à revisiter vers `httpOnly` si le projet grandit) ; pas de détection de réutilisation d'un refresh token révoqué comme signal d'alerte ; pas de vérification d'email à l'inscription ; pas de rate-limiting sur `/auth/login`/`/auth/signup`.

### 0.0.2 — Présentation de l'idée (texte libre ou import de document)

**Statut :** Complet.

Deux chemins à l'écran 4 : texte libre (`PATCH /projects/{id}`) ou import PDF (`POST /projects/{id}/upload-document`) avec extraction automatique (VLM Groq/Pixtral → LLM de structuration → 3 appels par table cible). Chaque champ extrait devient une ligne `project_field_values` (`en_attente`), pré-remplit directement les champs du formulaire des écrans 4 à 9 avec un encadré "valeur trouvée dans ton document", et la confirmation se fait implicitement au submit de l'écran (pas d'aller-retour API par champ).

**Choix clés :**
- Versionnement des documents (`documents`/`document_versions`) : un ré-upload crée une nouvelle version, jamais d'écrasement — historique conservé même si un seul document actif compte pour l'instant.
- Échec partiel de l'extraction non bloquant : le document reste importé même si un des 3 appels LLM échoue, l'erreur remonte pour information seulement — préférable à tout annuler alors que l'upload lui-même a réussi.
- `field_value` stocké en JSON (`json.dumps`) même pour un texte simple : les champs extraits couvrent plusieurs types Python, round-trip fiable sans table de correspondance séparée.

**Dette technique assumée :** `GET /projects/{id}/field-values` non rappelé après le premier upload (réutilise le retour de l'upload) — en cas de rechargement de page en plein onboarding, les champs en attente redeviennent invisibles jusqu'au prochain upload. Champs extraits sans écran dédié (`legal_form`, `siret`, `public_name`...) créés en base mais non affichés tant que la page "Mon Projet" n'existait pas (résolu depuis, voir Incrément 1 ci-dessous — Groupe 4 continue d'en dépendre).

### 0.0.3 — Questions contextuelles ciblées

**Statut :** Complet.

Écrans 5 à 8 (secteur/sous-secteurs/segments clients, cofondateurs/levée de fonds, technologies/proposition de valeur, localisation), tous facultatifs, même pattern (état local + brouillon `localStorage` + pré-remplissage par extraction + `PATCH /projects/{id}`). Écran 9 (vitrine publique, logo/site web) à cheval avec 0.0.4, entièrement facultatif (bouton "Passer").

**Choix clé :** calcul de complétion (`project_service._compute_completion`) recalculé à chaque écriture, jamais mis en cache — un écran sauté (ex. légal si startup non créée) sort du dénominateur plutôt que de compter comme manquant.

### 0.0.4 — Profil entrepreneur

**Statut :** Partiel / périmètre à clarifier.

`entrepreneur_profiles` est une table de liaison pure (`user_id` + timestamps), aucun champ métier — tous les faits déclaratifs vivent dans `Project`, pour permettre qu'un entrepreneur porte plusieurs projets un jour sans changer la structure. Le service 0.0.4 tel que nommé n'a donc pas de contenu fonctionnel propre : sa substance est en réalité portée par le questionnaire projet (0.0.2/0.0.3).

**Point non tranché :** à confirmer si ce périmètre est voulu, ou s'il manque un écran "profil personnel" distinct du profil projet.

Détail complet : `docs/Wink_schema_I0_entrepreneur.md`.

---

## Incrément 1 — Administratif & Création juridique de base (EPIC-01)

### Groupe 1 — Roadmap juridique + infrastructure d'embedding (copilot)

**Statut :** Complet et vérifié (24 nœuds en base, aucun orphelin).

Infrastructure transverse (pas un service numéroté) : tables `roadmap_nodes`/`roadmap_node_dependencies`/`startup_roadmap_items` (backend/entrepreneur) + `content_embeddings` (nouveau dossier `backend/shared/knowledge_base/`, transverse au copilot). Script `seed_roadmap_nodes.py` charge les 24 nœuds depuis un JSON, valide le graphe (dépendances orphelines + cycles par DFS), calcule les embeddings (BGE-M3, dense, 1024 dimensions) et les upsert.

**Choix clés :**
- `backend/shared/knowledge_base/` créé comme dossier transverse plutôt que dans `backend/entrepreneur/` : `content_embeddings` sert potentiellement plusieurs acteurs (recherche sémantique pas propre à l'entrepreneur).
- BGE-M3 plutôt que Qwen3-Embedding-8B (trop lourd) ou multilingual-e5-large (dépassé) : bon support du français, mode Sparse disponible plus tard si besoin de recherche hybride.
- Hébergement du modèle en lib Python locale pour l'instant (Option A), service séparé prévu plus tard (Option B) quand le copilot sera en usage réel.

**Dette technique assumée :** `startup_roadmap_items.statut` sans `CheckConstraint` (valeurs jamais formellement listées) ; chunking mono-chunk par nœud (suffisant tant que les nœuds restent courts) ; comportement `status → 'draft'` sur update de contenu non confirmé par l'utilisateur.

#### 1.1.11 — Plan d'action pré-création (roadmap + filtrage par profil)

**Statut :** Complet et vérifié (pipeline E2E jetable, `tsc`/`lint` propres hors erreurs préexistantes).

Suivi de progression sur les 24 nœuds du Groupe 1 (assignation au premier accès, statuts `verrouille`/`a_faire`/`en_cours`/`termine`/`non_necessaire`, déverrouillage en cascade le long du graphe de dépendances, dépôt de preuve documentaire par étape — PDF/PNG/JPEG, sans extraction). Frontend : page "Plan d'action" (nav de premier niveau, condition `project_type === "not_created"`), trois vues (Graphe / Sentier / Parcours) sur un moteur de layout pur (`roadmapLayout.ts`), popup de détail avec verdict 1.1.2 et bannière "Données utilisées".

**Choix clés :**
- **Filtrage à l'affichage, jamais à la sélection** : tous les nœuds sont assignés, et `roadmap_nodes.applicable_if` est évalué dans `list_roadmap` contre le profil réel du projet. Un nœud devenu inapplicable est masqué même s'il est `en_cours`/`termine` ; sa progression reste stockée.
- **Moteur applicable_if en sélecteur inverse** (`_apply_condition`) : opérateurs implémentés = `nb_cofondateurs_gte` (e4 pacte, fail-open si non renseigné), `objectifs_immediats_contains` (e23 dépôt de marque, condition sur une case cochée), `droits_de_vote_dirigeants_foyer_fiscal_gt` (e21 régime fiscal) ; tout opérateur futur inconnu = toujours satisfait.
- **e21 = union dirigeants ∪ foyer fiscal (décision qui remplace l'Option A "somme des dirigeants")** : la condition de l'art. 239 bis AB du CGI porte sur les dirigeants **et leur foyer fiscal** (conjoint/PACS/enfants, modélisé par un rattachement dans `project_associates`). Droits de vote NULL = proportionnels au capital ; fail-open si aucun dirigeant saisi (le nœud reste visible).
- **Dépendance Groupe 5 assumée** : la migration socle `project_associates` (avec colonne foyer fiscal) a été écrite en amont pour nourrir e21 avant même l'écran "Équipe & capital" (page couverte par le service du même nom, dont le récap détaillé reste à rédiger).

**Dette technique assumée / points non tranchés :** pas de tests unitaires PyTest versionnés sur le moteur `_apply_condition` (vérifié par E2E jetables) ; course de premier accès possible dans `_ensure_items` (deux requêtes concurrentes sur un projet vierge) non gérée ; `statut` sans CheckConstraint (dette Groupe 1 préexistante) ; fail-open différencié entre `nb_cofondateurs_gte` et `objectifs_immediats_contains` (champ à remplir vs case à cocher) à documenter pour les futurs opérateurs.

Détail complet : `docs/recap-service-1.1.11-plan-action-pre-creation.md`.

Détail complet (infrastructure Groupe 1) : `docs/recap-increment1-groupe1-roadmap-embeddings.md` *(project docs — pas encore rapatrié dans `wink/docs/`)*.

### Groupe 2 — Corpus réglementaire pour le copilot

#### 1.1.1 — Assistant de décision guidé (forme juridique)

**Statut :** Phases 1 à 3 complètes et vérifiées (75 articles, 155 chunks). Reste la Phase 4 (test manuel de retrieval sur une vraie question) avant de considérer le service vraiment terminé.

Collecte du corpus juridique (Code de commerce, SAS/SASU/SARL/EURL) via l'API Légifrance, classification et découpage par LLM (Groq), dashboard de validation humaine, embedding (BGE-M3) dans `content_embeddings`.

**Choix clé :** `forme_juridique_concernee` fixée par bloc (jamais devinée article par article par le LLM) — chaque bloc Légifrance correspond déjà à des formes juridiques connues d'avance.

**Bug corrigé en cours de route :** `strip_html()` collait les alinéas HTML sans frontière détectable (retirait `</p>`/`<br>` sans les remplacer par un saut de ligne), cassant le découpage par alinéa en Phase 2 — corrigé dans le pipeline permanent + 18 lignes concernées re-traitées.

**Dette technique assumée :** pas de rôle admin (dashboard accessible à tout compte connecté) ; emplacement `frontend/src/admin/` non couvert par `Wink_architecture_fichiers.md` (aucun acteur ne correspond à un outil interne) ; SCOP et micro-entreprise volontairement hors périmètre (identifiants non vérifiés).

Détail complet : `docs/recap-service-1.1.1-forme-juridique.md`.

#### 1.1.10 — Orientation sectorielle vers les assurances obligatoires

**Statut :** Implémenté (modèle, pipelines, dashboard, migration) mais **pas encore exécuté en conditions réelles** — collectes (Légifrance + web) pas encore lancées, validation humaine pas encore faite, embeddings pas encore générés, aucun test de retrieval.

Même logique que 1.1.1 (batch + validation humaine, jamais de génération live) appliquée aux obligations d'assurance par secteur startup (11 secteurs, 6 alias sémantiques rattachés). Deux volets de collecte : base légale (Légifrance, 8 blocs) et non-légal (guides professionnels, web).

**Choix clé — architecture volontairement isolée de 1.1.1 :** aucun fichier du pipeline `legal_texts` modifié, uniquement réutilisé quand déjà générique (`legifrance_client.py`, `legal_text_chunking_service.py`, `embedding_service.py`, `content_embeddings_service.py`). Contrainte explicite : pouvoir supprimer/modifier un pipeline sans risque de régression sur l'autre.

**Dette technique assumée :** couverture du volet non-légal partielle (4 secteurs sur 11 à ce stade) ; matching secteur utilisateur (texte libre) → secteur collecté pas encore implémenté (nécessitera une classification sémantique, hors périmètre de cette collecte) ; comportement pour un secteur hors périmètre cadré mais pas codé ; logique de retry Groq dupliquée avec `legal_text_structuring_service.py` (factorisation différée tant qu'un 3e pipeline n'apparaît pas).

Détail complet : `docs/recap-service-1.1.10-assurances-sectorielles.md`.

### Groupe 4 — Services indépendants du copilot

#### 1.1.2 — Vérificateur de disponibilité du nom

**Statut :** Complet.

Recherche croisée sur deux API publiques : Recherche d'Entreprises (dénomination sociale, sans auth) et Base Marques INPI (dépôt de marque, compte personnel authentifié). Historique append-only (`name_availability_checks`, une ligne par vérification, aucune contrainte d'unicité — un nom peut être re-testé). Affichage en verdict synthétisé (badge rouge/orange/vert) dans `StepDetailPopup.tsx`, calculé côté client depuis une règle métier fixe, avec le détail Nom/Marque gardé en badges secondaires.

**Choix clés :**
- Authentification INPI intégralement reverse-engineered et vérifiée par appels réels (flow CSRF en 3 étapes, requête par phrase exacte obligatoire entre guillemets — sans quoi la recherche devient un plein-texte large donnant de faux négatifs, réponse en JSON via `Accept` explicite malgré un `Content-Type` trompeur renvoyé par le serveur).
- Verdict calculé côté client (pas stocké en base) : c'est une règle d'interprétation fixe, pas une donnée propre à chaque ligne d'historique — décision validée par mockup Artifact avant implémentation.

**Point produit resté ouvert :** le statut INPI "Demande publiée" (dépôt en cours) n'est pas traité comme bloquant actuellement — à trancher si une demande en cours doit compter comme "risque".

Détail complet : voir `marques_client.py` (docstring module, section "VÉRIFIÉ") — pas encore de `recap-service-1.1.2-*.md` dédié.

#### 1.1.17 — Coffre-fort documentaire

**Statut :** Vue documents + téléchargement de la version courante complets et vérifiés en conditions réelles. Extension historique des versions, refonte UX de la liste/historique, et aperçu de document en tiroir glissant : toutes implémentées, **pas encore testées dans le navigateur** (voir détail de chaque pièce plus bas).

Vue de consultation centralisée des documents du projet, groupée par `document_type` — aucune nouvelle table, pure lecture sur `documents`/`document_versions` (I0). `GET /projects/{id}/documents` (`document_vault_router.py`/`_service.py`/`_schemas.py`) renvoie chaque document enrichi des champs de sa dernière version (nom de fichier, taille). 4e carte sur la page "Mon Projet" → `DocumentVaultPage.tsx`, sous le même `MyProjectLayout` que les 3 autres sections (pas de second `GET /projects/me`).

**Choix clés :**
- Fichiers séparés de `document_router.py`/`document_service.py` (scopés au service 0.0.2, upload + extraction) : même principe que `name_availability_router.py` vs `project_router.py` — une responsabilité par fichier même si la table `documents` est partagée entre les deux services.
- `DocumentType` réimporté depuis `document_schemas.py` plutôt que redéfini dans `document_vault_schemas.py` : une seule source de vérité sur les valeurs autorisées par le `CHECK` constraint.
- `outerjoin` (pas `join`) entre `documents` et `document_versions` : `current_version_id` est nullable en base, un document sans version encore rattachée doit rester visible plutôt que disparaître silencieusement de la liste.

**Limite connue, assumée dès la conception (voir `docs/plan-implementation-groupe4.md`) :** `documents.document_type` n'autorise aujourd'hui que `'entrepreneur_idea'`/`'other'` (`CHECK` constraint I0). Le coffre-fort n'affichera donc que les documents importés à l'onboarding tant que 1.1.4/1.1.9/etc. n'existent pas et n'ajoutent pas leurs propres valeurs de type — pas un bug, un état transitoire attendu.

**Bug trouvé et corrigé en cours de route — téléchargement de document illisible :**

Root cause : `cloudinary_service.upload_raw_file()` uploadait les documents (`resource_type="raw"`) sans `public_id` explicite. Cloudinary générait alors un identifiant sans extension, donc une `secure_url` du type `.../c7yupeysieesgz0afk4e` (pas `.pdf`) — le fichier téléchargé était syntaxiquement valide (vérifié directement) mais l'OS ne savait pas quelle application l'ouvrir. Corrigé pour les futurs uploads : `public_id` construit désormais comme `{uuid}{extension}` à partir du nom de fichier original.

Pour les documents déjà uploadés avant ce correctif (toujours sans extension en base), une première tentative de contournement à la lecture — flag Cloudinary `fl_attachment:<nom>` pour forcer nom+extension au moment du téléchargement (`cloudinary_service.build_raw_download_url()`) — a été **testée en conditions réelles par l'utilisateur et a échoué deux fois (HTTP 400)**, probablement une restriction Cloudinary sur les transformations appliquées aux ressources `raw`. Abandonnée (fonction supprimée) au profit d'une solution qui ne dépend plus du tout du comportement de transformation Cloudinary :

- Nouvelle route `GET /projects/{id}/documents/{document_id}/download` : le backend récupère lui-même les octets depuis `secure_url` (`requests.get`, sans transformation) et les sert avec son propre header `Content-Disposition: attachment; filename="..."`, indépendamment de ce que Cloudinary expose.
- Champ `download_url` retiré du schéma de liste (`DocumentVaultItemRead`) — n'avait plus de sens une fois le téléchargement passé par une route authentifiée plutôt qu'une URL statique.
- Frontend : `documentVaultApi.ts` fait un `fetch()` authentifié (`Authorization: Bearer`) vers la nouvelle route et retourne un `Blob` — un `<a href>` classique ne peut pas porter ce header. `DocumentVaultPage.tsx` déclenche ce fetch au clic sur un bouton (plus un lien direct), puis simule un clic sur un `<a download>` temporaire via `URL.createObjectURL`.

**Pourquoi cette approche plutôt qu'insister sur Cloudinary :** deux échecs réels confirmés suffisent à abandonner une piste qui dépend d'un comportement de plateforme externe non documenté/non garanti pour ce compte, plutôt que de continuer à deviner une variante de flag qui pourrait fonctionner. Le proxy backend est plus verbeux (une requête HTTP de plus par téléchargement) mais entièrement sous notre contrôle.

**Extension — historique des versions :**

Le versionnement existait déjà en base depuis 0.0.2 (`document_versions.document_id`/`version_number`, un ré-upload crée une ligne plutôt que d'écraser), mais aucune route ni écran ne l'exposait — 1.1.17 se limitait à la version courante de chaque document. Ajout de :

- `GET /projects/{id}/documents/{document_id}/versions` (`document_vault_service.list_document_versions`) : tout l'historique d'un document, plus récente en premier, chaque ligne marquée `is_current`.
- `GET /projects/{id}/documents/{document_id}/versions/{version_id}/download` (`get_document_version_download`) : téléchargement d'une version précise, même mécanisme proxy backend que la version courante (`_fetch_version_bytes()` factorisé entre les deux pour ne pas dupliquer l'appel réseau + la gestion d'erreur Cloudinary).
- Frontend : accordéon par document dans `DocumentVaultPage.tsx` — bouton "Historique" qui charge la liste à la demande (pas de préchargement pour tous les documents au montage de la page, la plupart ne seront jamais ouverts) et affiche chaque version avec son propre bouton de téléchargement.

**Compromis assumé :** l'historique n'est pas mis en cache côté frontend — rouvrir un document déjà consulté refait l'appel réseau. Acceptable pour une vue de consultation peu fréquentée ; à revoir si l'usage réel montre que les utilisateurs rouvrent souvent le même historique.

**Non encore vérifié :** cette extension (historique + téléchargement par version) n'a pas encore été testée dans le navigateur — seul le correctif de téléchargement de la version courante ci-dessus est confirmé.

**Refonte UX de la liste + de l'historique :** l'implémentation initiale (liste `divide-y` brute, bouton "Historique" en texte gris minuscule, panneau en fond gris plat, version en `text-xs`, badge "actuelle" en simple mot ajouté) a été jugée peu lisible. Critique détaillée + proposition comparée en direct produites dans un artefact avant tout changement de code, puis implémentée telle quelle après validation :

- Chaque document est désormais sa propre carte (`rounded-lg border`) avec icône de type de fichier (`bg-indigo-50`/`text-indigo-600`, palette de l'app — pas la palette bespoke de l'artefact de démo), bouton de téléchargement dédié (icône seule) et, seulement si `version_count > 1`, un chip pilule "N versions" à chevron animé.
- Historique en timeline verticale (point relié par une ligne entre versions), badge "Actuelle" en ambre (`bg-amber-50`/`text-amber-700` — réutilise la palette sémantique déjà utilisée dans `StepDetailPopup.tsx`/`StepNode.tsx` pour les statuts, plutôt que d'introduire une nouvelle couleur).
- Icônes en SVG inline à la main (`viewBox 0 0 24 24`, `strokeWidth={2}`), même convention que `VerdictIcon` dans `StepDetailPopup.tsx` — pas de librairie d'icônes ajoutée au projet pour 3 pictogrammes.
- Ajout de `DocumentVaultItemRead.version_count` (backend) : sous-requête groupée (`GROUP BY document_id`) jointe à la requête principale, pas un `COUNT()` par document dans la boucle Python (N+1) — permet au frontend de masquer le chip "Historique" sans requête supplémentaire par document.

**Choix de conception explicite :** la palette de l'artefact de démo (teal/or) n'a pas été reprise telle quelle dans le vrai code — l'app a déjà un langage visuel (indigo-600 en accent principal, ambre en couleur sémantique secondaire, gris neutres), donc l'implémentation réelle s'y conforme plutôt que d'introduire une identité visuelle parallèle. L'artefact servait à valider l'interaction et la hiérarchie, pas les couleurs exactes.

**Aperçu de document en popup :** clic sur le nom d'un document (plutôt que sur le bouton télécharger) ouvre son contenu dans une popup, sans quitter le coffre-fort.

- Réutilise `shared/components/Modal.tsx` (déjà utilisé ailleurs dans l'app — Échap/clic dehors déjà gérés) plutôt qu'un nouveau composant de popup : `Modal` gagne une prop `size` optionnelle (`"md"` par défaut = comportement inchangé pour tous les appelants existants, `"xl"` = plus large, ajoutée pour ce cas). Popup choisie plutôt qu'un panneau latéral car aucun pattern de panneau latéral n'existe ailleurs dans l'app — éviter d'introduire un second paradigme d'UI pour un seul cas d'usage.
- Nouveau composant `entrepreneur/components/DocumentPreviewModal.tsx` : récupère le fichier via les mêmes endpoints authentifiés que le téléchargement (`downloadDocument`/`downloadDocumentVersion`, réutilisés tels quels), affiche un `<iframe>` pour un PDF (visualiseur natif du navigateur, aucune dépendance PDF.js ajoutée) ou une `<img>` pour une image, avec un repli "aperçu non disponible" + bouton télécharger pour tout autre type — un document du coffre-fort n'est pas garanti être un PDF à long terme (1.1.4/1.1.9 pourront y déposer d'autres types).
- Le type MIME utilisé pour choisir le rendu vient de `blob.type` (posé par le navigateur depuis le `Content-Type` de la réponse), pas d'une prop séparée à faire suivre depuis la liste.
- `triggerBlobDownload()` extrait de `DocumentVaultPage.tsx` vers `entrepreneur/utils/blobDownload.ts` (même convention qu'`utils/fieldValueFormat.ts` etc.) : maintenant utilisé à la fois par la page et par le repli de la popup, éviter de le dupliquer.
- Composant réutilisable pour une version historique aussi (`versionId` optionnel en prop) même si non branché sur les lignes d'historique pour l'instant — pas demandé dans cette itération, ajout trivial si besoin plus tard (passer `version.id` au lieu d'omettre la prop).

**Placement de l'aperçu — popup, panneau split ou tiroir :** trois placements comparés dans un artefact interactif (mockup cliquable des 3 modes, comparatif avantages/inconvénients) avant tout code. Choix retenu par l'utilisateur : **tiroir qui glisse depuis la droite**. Raison de la recommandation suivie : coût d'implémentation proche de la popup (composant qui se pose par-dessus la page, pas de refonte de layout comme le split), mais moins bloquant — la liste reste visible en arrière-plan derrière le fondu.

- Nouveau composant partagé `shared/components/Drawer.tsx` (Échap + clic dehors, même mécanique que `Modal.tsx`) plutôt qu'une variante de `Modal` : le positionnement (ancré plein-hauteur à droite, transition de glissement) diffère trop d'un popup centré pour rester lisible derrière une seule prop. Transition en CSS pure (`translate-x`), aucune dépendance d'animation Tailwind ajoutée — monté hors écran puis basculé au prochain repaint via un état `isOpen`. Pas d'animation de sortie (fermeture immédiate), même choix que `Modal.tsx`.
- `DocumentPreviewModal.tsx` bascule de `Modal` (`size="xl"`) vers `Drawer` — la prop `size` de `Modal.tsx` a donc été retirée (elle n'avait plus aucun appelant, laisser une variante inutilisée aurait été de la complexité morte).
- **Dette mineure assumée :** `DocumentPreviewModal.tsx` garde son nom de fichier malgré le passage en tiroir (devrait être `DocumentPreviewDrawer.tsx`) — le pont vers l'ordinateur de l'utilisateur ne permet pas de renommer/supprimer un fichier proprement depuis cette session (pas d'accès `device_bash` fiable sur cette machine). À renommer manuellement si souhaité ; documenté dans le docstring du fichier pour qu'un futur lecteur ne soit pas surpris par le nom.

Détail complet : pas encore de `recap-service-1.1.17-*.md` dédié (service compact, couvert intégralement par cette entrée + les docstrings des fichiers).

#### 1.1.18 (provisoire) — Vérification croisée SIREN/SIRET

**Statut :** Implémenté (backend + frontend). Plusieurs tests réels par l'utilisateur ont fait remonter 5 bugs, tous corrigés (détail plus bas) : le 422 bloquant sur la sauvegarde, l'UX du panneau de résultat, la requête vers l'API Recherche d'Entreprises qui ne trouvait jamais aucune entreprise (mauvaise syntaxe de paramètre), le rafraîchissement de la page après fermeture de la modale via le "×" (jamais déclenché), et le SIRET jamais réellement vérifié malgré le badge. **Pas encore re-testé après ces 2 dernières corrections.**

Numéro provisoire : ce service n'a pas encore de numéro officiel dans le plan Groupe 4, noté "1.1.18" en attendant. Concerne uniquement Parcours B (`project_type = "created"`) pour l'instant ; conçu pour être réutilisé par le futur 1.1.9 (Parcours A, job périodique une fois le SIREN attribué par le Guichet Unique).

**Pourquoi ce service et pourquoi maintenant :** en travaillant l'ordre d'implémentation de Parcours A, un blocage réel est apparu — le service Kbis (1.1.9) suppose qu'un SIREN existe déjà sur le projet, ce qui n'est vrai qu'après la Vague 2 (Guichet Unique, actuellement bloquée sur un accès API non confirmé). Plutôt que d'attendre, la vérification SIREN/SIRET de Parcours B (startup déjà créée) a été avancée : elle est testable dès maintenant (l'utilisateur saisit son propre SIREN à l'onboarding) et son cœur (`legal_verification_service.verify_legal_profile`) sera repris tel quel par 1.1.9 plus tard — un seul endroit où vit la logique de vérification, deux déclencheurs différents (bouton HTTP ici, script périodique plus tard).

**Décision UX actée avant le code (voir artefact "Vérification SIREN" validé par l'utilisateur) :** séparation stricte entre contrôle de format (gratuit, local, instantané) et vérification réelle (appel externe, peut échouer/être lent) :

- **Onboarding (Écran 3, `LegalProfilePage.tsx`) :** uniquement un contrôle de format SIREN par l'algorithme de Luhn (`entrepreneur/utils/luhn.ts`), en local, **aucun appel réseau**. Bloque la soumission si le format est invalide (bouton désactivé), mais ne confirme jamais que l'entreprise existe réellement. L'inscription ne doit jamais dépendre du bon fonctionnement d'un service externe.
- **"Mon Projet" → Informations légales (`ProjectLegalInfoPage.tsx` / `UpdateLegalProfileForm.tsx`) :** la vraie vérification est déclenchée explicitement, au clic sur "Mettre à jour", **après** la sauvegarde (PATCH). Save et verify sont deux appels séparés : un échec de la vérification (API externe indisponible, 503) ne remet jamais en cause la sauvegarde des champs saisis.

**Backend :**

- `scrapers/recherche_entreprises/client.py` — ajout de `get_by_siren(siren)`, réutilise l'endpoint déjà utilisé par 1.1.2 (`GET .../search?q=siren:...`). Retourne `None` si le SIREN est introuvable/inactif (pas une erreur).
- `backend/entrepreneur/services/legal_verification_service.py` (nouveau fichier, séparé de `project_service.py` — même raison que `name_availability_service.py` pour 1.1.2 : cette logique dépend d'un appel externe avec ses propres échecs) — `verify_legal_profile()` : lit le SIREN déjà enregistré sur `project_legal_profiles`, appelle `get_by_siren`, met à jour les 3 statuts (`denomination_verification_status`, `immatriculation_verification_status`, `kbis_verification_status`). SIREN introuvable → les 3 restent `non_verifie`. SIREN trouvé → immatriculation et Kbis passent à `verifie` (un seul appel confirme les deux, même instant/même source) ; dénomination passe à `verifie` ou `incoherent` selon que le nom saisi correspond au nom officiel (comparaison insensible casse/accents via `scrapers/shared/text_normalize.fold`, déjà utilisé par 1.1.2).
- `backend/entrepreneur/routes/project_router.py` — nouvelle route `POST /projects/{id}/legal-profile/verify`, volontairement séparée du `PATCH .../legal-profile` existant. `_handle_project_error` étendu pour mapper une erreur de l'API externe en 503 (pas 400 — ce n'est pas une erreur de saisie utilisateur), même convention que `name_availability_router.py`.

**Frontend :**

- `entrepreneur/utils/luhn.ts` (nouveau) : `isValidSirenFormat()`, pure fonction locale.
- `entrepreneur/pages/LegalProfilePage.tsx` : champ SIREN avec filtrage des caractères non numériques à la saisie. Le contrôle Luhn ne se déclenche qu'au clic sur "Continuer" (pas de retour visuel qui change à chaque frappe — voir correctif ci-dessous, comportement initial revu après retour utilisateur) ; un format invalide affiche un message d'erreur et bloque la soumission.
- `entrepreneur/api/projectApi.ts` : ajout de `verifyLegalProfile()`.
- `entrepreneur/components/VerificationStatusBadge.tsx` (nouveau) : badge réutilisable pour un statut (`non_verifie`/`verifie`/`incoherent`), utilisé à 2 endroits ci-dessous.
- `entrepreneur/components/UpdateLegalProfileForm.tsx` : après une sauvegarde réussie, si `isCreated` et qu'un SIREN est enregistré, déclenche `verifyLegalProfile()` et affiche un panneau de résultat (3 badges) à la place de la fermeture automatique ; un échec de la vérification affiche un message sans perdre la saisie déjà sauvegardée.
- `entrepreneur/pages/ProjectLegalInfoPage.tsx` : affichage permanent des 3 badges en haut de la section "Immatriculation" (lecture seule — mis à jour uniquement via le formulaire ci-dessus, jamais par un appel automatique sur cette page).

**Points ouverts / dette assumée :**

- La structure exacte de la réponse de l'API Recherche d'Entreprises (clé `results`, champs `nom_complet`/`nom_raison_sociale`) est reprise de la documentation publique mais **n'a pas pu être confirmée par un appel réel** depuis cet environnement — à vérifier au premier test en conditions réelles.
- Aucune des 4 valeurs de statut n'existe pour "SIREN introuvable" : un SIREN au format valide mais introuvable laisse les 3 statuts à `non_verifie`, indiscernable côté UI d'un profil jamais vérifié. Comportement voulu par la spec historique (Groupe 4), pas un oubli — à revisiter si ça s'avère peu clair à l'usage.
- 1.1.9 (Parcours A, Vague 3) n'est pas encore implémenté — reste à écrire le script/job périodique qui appelle `legal_verification_service.verify_legal_profile()` et, en plus, crée une notification (table `notifications`, déjà migrée) quand le SIREN passe de non attribué à attribué.

**Corrections après premier test réel (2 bugs) :**

1. **UX onboarding trop bavarde à la saisie.** La première version validait le format Luhn à chaque caractère tapé (bordure rouge/verte, texte "Format valide/invalide" changeant en direct, bouton "Continuer" désactivé pendant la frappe). Jugé intrusif à l'usage réel. Corrigé : le contrôle ne se déclenche plus qu'au clic sur "Continuer" — aucun retour visuel pendant la saisie, juste un message d'erreur si le format est invalide au moment de soumettre.

2. **422 bloquant sur `PATCH .../legal-profile` (bug réel, pas un simple ajustement UX).** Root cause : `siret` (et `siren`) sont validés côté backend par un pattern Pydantic strict (`^\d{14}$` / `^\d{9}$`, voir `project_legal_profile_schemas.py`). Une chaîne vide `""` n'est **pas** équivalente à "champ non fourni" pour cette validation — un SIRET vide envoyé dans le payload faisait donc échouer toute la requête en 422, avant même d'atteindre la logique métier. `UpdateLegalProfileForm.tsx` envoyait `siret: siret.trim()` inconditionnellement (contrairement à `registration_date`, déjà omis quand vide) : corrigé en appliquant le même traitement "omettre si vide" à `siren`/`siret`. `legal_name`/`legal_form`/`registration_number`/`vat_number`/`naf_code` n'ont qu'une contrainte de longueur (pas de pattern) — une chaîne vide y reste valide, donc laissés inchangés (toujours envoyés, permet de vider volontairement ces champs) : pas de sur-correction au-delà du besoin réel.
   - **Anti-pattern à retenir :** sur un champ Pydantic `Optional[str]` avec un `pattern`, seul `None`/absence du champ contourne la validation — une chaîne vide `""` est une valeur comme une autre et reste soumise au pattern. Un formulaire qui traite "champ laissé vide" et "champ non touché" de la même façon (chaîne vide) percute ce piège dès qu'un champ optionnel a une contrainte de format.
   - **Bug annexe corrigé au passage :** l'écran affichait `[object Object]` au lieu du message d'erreur. Cause : FastAPI renvoie `detail` comme un **tableau** d'erreurs de validation Pydantic (`[{loc, msg, type}, ...]`) sur un 422, pas une chaîne — alors que les clients HTTP du frontend (`authApi.ts`, `projectApi.ts`) supposaient `detail` toujours string. `new ApiError(status, detail)` avec `detail` = ce tableau donnait ce rendu (`Error` convertit une valeur non-string via `toString()`). Corrigé une seule fois (`parseErrorDetail()` dans `authApi.ts`, exporté et réutilisé par `projectApi.ts`) plutôt que dans chaque fichier `*Api.ts` — bug latent qui pouvait resurgir sur n'importe quel endpoint renvoyant une erreur de validation Pydantic brute, pas seulement celui-ci.

**Reste à faire avant de passer au service suivant :** re-test par l'utilisateur du flux complet ("Mettre à jour" avec un SIREN réel) pour confirmer que le 422 est bien résolu et que l'appel à l'API Recherche d'Entreprises fonctionne comme prévu.

**Correction UX après ce re-test réel (le 422 est résolu) :** le résultat de la vérification s'affichait à la place du formulaire (tout le formulaire disparaissait, remplacé par le panneau de badges + bouton "Fermer"), jugé trop brutal — perte de contexte de ce qui venait d'être saisi. Proposition validée par l'utilisateur avant implémentation (voir échange) : le résultat s'affiche maintenant **sous le formulaire**, qui reste entièrement visible et modifiable.

*Correction à cette étape : l'affirmation "l'appel réel fonctionne" plus haut était prématurée — le test qui la motivait montrait "Non vérifié" sur les 3 statuts, ce qui est indiscernable en apparence entre "SIREN introuvable" (comportement normal) et "la requête à l'API est mal construite" (bug). Voir bug ci-dessous, trouvé juste après grâce à un test avec un SIREN réel connu.*

- `UpdateLegalProfileForm.tsx` : suppression du `return` anticipé qui remplaçait tout le rendu par le panneau de résultat. Le bloc résultat ("Résultat de la vérification") est maintenant rendu après la ligne de boutons, dans le même `<form>`. L'utilisateur peut corriger un champ et ré-enregistrer sans fermer la modale — chaque nouvel "Enregistrer" relance sauvegarde + vérification et remplace le résultat affiché.
- Bouton "Annuler"/"Fermer" fusionné en un seul bouton dont le libellé et le comportement changent selon la phase : "Annuler" tant que rien n'est sauvegardé (ferme simplement, `onCancel`) ; "Fermer" une fois un résultat affiché (ferme **et** déclenche le rafraîchissement du profil côté page parente via `onSaved`, pour que l'affichage permanent des badges dans `ProjectLegalInfoPage.tsx` reflète la nouvelle vérification sans re-chargement manuel).
- Libellé du badge "Immatriculation" renommé en **"SIREN / SIRET"** (affichage seulement, la donnée reste `immatriculation_verification_status`) — plus clair pour l'utilisateur sur ce que ce badge couvre réellement. Appliqué aux deux endroits où ce badge apparaît : le nouveau panneau de résultat et l'affichage permanent de `ProjectLegalInfoPage.tsx`.
- Ajout d'un encart orange explicatif quand `denomination_verification_status === "incoherent"` ("Le nom officiellement enregistré diffère de celui saisi. Vos informations sont enregistrées quand même — corrigez si c'est une erreur de saisie, ou ignorez si c'est normal.").
- **Limite assumée :** cet encart ne cite pas le nom officiel trouvé (ex: "« WINK TECHNOLOGIES SAS »") — `legal_verification_service.verify_legal_profile()` calcule ce nom pour la comparaison mais ne le renvoie/stocke pas actuellement. Message resté générique plutôt que d'inventer une donnée non disponible côté frontend ; ajout possible plus tard (renvoyer ce nom comme champ éphémère de la réponse de `/legal-profile/verify`, sans le persister) si l'utilisateur le souhaite — pas fait maintenant pour rester au périmètre demandé (le retour portait sur le placement, pas sur le contenu du message).

**Bug réel trouvé et corrigé — l'appel à l'API ne trouvait JAMAIS aucune entreprise.** En fournissant des exemples de test à l'utilisateur (SIREN réels et vérifiés d'entreprises connues, ex. Doctolib `794598813`), le test a montré "Non vérifié" sur les 3 statuts — alors que Doctolib est une entreprise bien réelle et active. Impossible à distinguer, avant investigation, d'un cas "SIREN introuvable" normal.

Root cause : `get_by_siren()` construisait la requête avec `q=siren:{siren}` (syntaxe à préfixe `champ:valeur`), reprise du README d'un dépôt public tiers autour de cette API — **cette syntaxe n'existe pas côté serveur**. Testé en réel : `?q=siren:794598813` renvoie 0 résultat, `?q=794598813` (le SIREN tel quel, sans préfixe) renvoie bien la fiche Doctolib. Confirmé aussi contre la doc OpenAPI officielle de l'API, qui documente `q` comme acceptant "une recherche textuelle... ou une recherche directe (SIREN, SIRET)" — sans mention d'une syntaxe à préfixe.

- Corrigé dans `scrapers/recherche_entreprises/client.py` : `get_by_siren()` envoie maintenant `params={"q": siren, ...}` au lieu de `params={"q": f"siren:{siren}", ...}`.
- Ce bug touchait uniquement `get_by_siren()` (donc ce service et le futur 1.1.9) — `search_by_name()` (1.1.2) construit déjà `q` avec le nom brut, sans préfixe, non affecté.
- **Leçon retenue :** un exemple de code trouvé dans la documentation d'un tiers (même un dépôt public gravitant autour de la même API officielle) n'est pas une garantie de fonctionnement — seul un appel réel contre l'API en fait foi. Le module documentait déjà cette incertitude ("à confirmer au premier appel réel") avant ce test ; la docstring de `client.py` est mise à jour pour refléter ce qui est maintenant réellement confirmé.
- Les exemples de test (Doctolib, BlaBlaCar/Comuto, Criteo) donnés à l'utilisateur restent valides — c'était la requête, pas les données, qui était fausse.

**Bug réel trouvé et corrigé — la page "Informations légales" n'affichait pas les nouvelles valeurs après une mise à jour.** Signalé par l'utilisateur : après avoir mis à jour son profil légal, il fallait recharger la page entière pour voir le changement. Root cause : `Modal` (le "×" natif en haut à droite de la fenêtre "Mettre à jour") avait son propre `onClose` câblé directement à `() => setIsUpdateModalOpen(false)` dans `ProjectLegalInfoPage.tsx` — sans jamais appeler `reloadLegalProfile()`/`refresh()`. Seul le bouton interne "Annuler"/"Fermer" du formulaire déclenchait ce rafraîchissement (ajouté lors de la correction UX précédente) ; fermer via le "×" le contournait entièrement.

- Corrigé en unifiant les deux chemins de fermeture : `ProjectLegalInfoPage.tsx` expose maintenant une seule fonction `closeUpdateModal()` (ferme + `reloadLegalProfile()` + `refresh()`), passée à la fois à `Modal` (`onClose`) et à `UpdateLegalProfileForm` (nouvelle prop unique `onClose`, remplace les anciennes `onSaved`/`onCancel` séparées).
- Rafraîchir systématiquement au lieu de conditionner sur "est-ce qu'une sauvegarde a eu lieu" est un choix délibéré de simplicité : un GET de plus quand rien n'a changé est sans coût réel, et évite la classe de bug rencontrée ici (un chemin de fermeture oublié).

**Bug réel trouvé et corrigé — le SIRET n'était jamais vérifié malgré le badge "SIREN / SIRET".** L'utilisateur a testé avec un SIRET manifestement faux (`12121212121213`) et a quand même obtenu "Vérifié" — a demandé explicitement quels champs sont réellement vérifiés. Réponse honnête : `verify_legal_profile()` ne vérifiait que le SIREN (clé de recherche) et la dénomination (comparée au nom retourné) ; le SIRET saisi n'était jamais comparé à rien. Le renommage du badge en "SIREN / SIRET" (fait plus haut dans cette même entrée) était donc trompeur.

Corrigé, avec l'accord explicite de l'utilisateur (vraie vérification plutôt que renommer le badge en "Immatriculation") :

- `legal_verification_service.py` : le SIRET du siège social est maintenant extrait de la réponse API (`result["siege"]["siret"]`, confirmé par appel réel) et comparé au SIRET saisi, quand un SIRET a été renseigné. S'il ne correspond pas, `immatriculation_verification_status` passe à `"incoherent"` (au lieu de `"verifie"`) — même traitement que la dénomination. Aucun SIRET saisi → pas de comparaison possible, le statut reste basé sur le SIREN seul (comportement inchangé).
- `kbis_verification_status` continue de suivre `immatriculation_verification_status` (y compris `"incoherent"`) — pas de vérification séparée du document Kbis lui-même, décision déjà actée (voir plus haut), pas de changement de portée ici.
- `UpdateLegalProfileForm.tsx` : ajout d'un 2ᵉ encart explicatif (même style que celui de la dénomination) quand `immatriculation_verification_status === "incoherent"`, avec un cas limite signalé honnêtement dans le message ("ignorez si c'est normal (ex: un établissement secondaire)" — un SIRET différent du siège social n'est pas forcément une erreur de saisie).
- **Ce qui reste non vérifié, assumé** : N° TVA, Code NAF, Numéro d'immatriculation, Date d'immatriculation. Aucun de ces champs n'a de contrepartie comparée dans la réponse de l'API actuellement exploitée — pas dans le périmètre de cette correction (l'utilisateur a demandé la clarté sur ce qui est vérifié, pas d'étendre la vérification à tous les champs).

---

## Comment utiliser ce fichier

1. Une entrée par service terminé, sous son Groupe/Incrément — jamais de suppression, seulement des ajouts ou des mises à jour de statut (ex. "Phase 4 restante" → "Phase 4 complète").
2. Rester au niveau **choix + pourquoi + dette technique/points ouverts** — le détail fichier par fichier va dans un `docs/recap-service-X.md` séparé quand il existe, référencé ici.
3. Un service "implémenté mais pas encore exécuté/vérifié" (ex. 1.1.10) reste documenté ici avec son statut réel — ne pas attendre l'exécution complète pour l'ajouter, mais ne jamais le présenter comme "Complet" tant que ce n'est pas vérifié.
