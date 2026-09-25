/**
 * Client HTTP pour `backend/entrepreneur/routes/project_router.py` — un fichier,
 * une responsabilité : parler à l'API `/projects`, rien d'autre (pas de state,
 * voir `entrepreneur/context/OnboardingWizardContext.tsx` pour ça).
 *
 * Toutes les routes sont protégées côté backend (Depends(get_current_user)), donc
 * chaque fonction ici prend l'access token en premier paramètre — même convention
 * que `getCurrentUser` dans `shared/api/authApi.ts`.
 */
import { ApiError, parseErrorDetail } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ProjectType = "not_created" | "created"
export type ProjectStage = "ideation" | "pre_seed" | "seed" | "serie_a"
export type ProjectSourceType = "texte_libre" | "document_importe"
export type ProjectProfileCompletion = "incomplet" | "complet"
// Reflète le CheckConstraint sur project_public_profiles (voir
// projectVisibilityOptions.ts pour les libellés affichés).
export type ProjectVisibility = "private" | "public" | "investors_only"

export interface ProjectRead {
  id: string
  entrepreneur_profile_id: string
  project_type: ProjectType
  stage: ProjectStage
  description: string | null
  source_type: ProjectSourceType | null
  imported_document_id: string | null
  nombre_cofondateurs: number | null
  intention_levee_fonds: boolean | null
  // Objectifs immédiats (ex: ["protection_marque_code"]) — question onboarding
  // Écran 6, sert au filtrage de la roadmap (1.1.11). (réalisé par OPENCODE)
  objectifs_immediats: string[]
  localisation: string | null
  sector: string | null
  subsectors: string[]
  customer_segments: string[]
  target_users: string[]
  technologies: string[]
  value_proposition: string | null
  project_profile_completion: ProjectProfileCompletion
  completion_percentage: number
  created_at: string
  updated_at: string
}

/** Une résolution explicite pour un champ extrait affiché sur l'écran — envoyée
 * dans le MÊME payload que le PATCH ("confirmation globale", voir DECISIONS),
 * jamais en appel séparé. Le frontend sait déjà, au moment de l'affichage
 * inline, si l'utilisateur a touché ou ignoré ce champ : jamais déduit par
 * comparaison de valeurs côté backend. */
export type ResolutionAction = "confirme" | "corrige" | "ignore"

export interface FieldValueResolution {
  id: string
  action: ResolutionAction
}

export interface ProjectUpdate {
  project_type?: ProjectType
  stage?: ProjectStage
  description?: string
  nombre_cofondateurs?: number
  // null explicite = remettre à "pas encore décidé" (voir ProjectUpdate côté
  // backend, qui accepte bool | None) ; undefined = champ non touché par ce PATCH.
  intention_levee_fonds?: boolean | null
  // Liste complète (pas un diff) — ex: ["protection_marque_code"]. (réalisé par OPENCODE)
  objectifs_immediats?: string[]
  localisation?: string
  sector?: string
  subsectors?: string[]
  customer_segments?: string[]
  target_users?: string[]
  technologies?: string[]
  value_proposition?: string
  resolved_field_values?: FieldValueResolution[]
}

export interface ProjectLegalProfileCreate {
  legal_name?: string
  legal_form?: string
  registration_number?: string
  siren?: string
  siret?: string
  vat_number?: string
  naf_code?: string
  registration_date?: string
  registered_address?: Record<string, unknown>
  // Depuis la migration e1b2c3d4e5f6, le représentant légal est un ASSOCIÉ (FK →
  // project_associates), plus un objet JSON libre. Voir ProjectAssociateRead.
  legal_representative_associate_id?: string
  objet_social?: string
  duree_societe?: number
  date_signature_statuts?: string
  // Lot 1 (24/09/2026, service 1.1.4) : lus automatiquement par les statuts
  // (Art. 2, 3, 6, 7 et clôture) -- voir StatutsRedactionFields.tsx.
  // Montants en chaîne : le backend (Decimal) les sérialise ainsi.
  sigle?: string
  raison_d_etre?: string
  objectifs_ess?: string
  lieu_signature_statuts?: string
  capital_social?: string
  nombre_actions?: number
  valeur_nominale?: string
  lieu_immatriculation?: string
}

/** PATCH /projects/{id}/legal-profile (upsert, voir project_service.update_legal_profile) —
 * tous les champs optionnels, contrairement à ProjectLegalProfileCreate qui sert au
 * premier remplissage (écran 3 de l'onboarding). */
export interface ProjectLegalProfileUpdate {
  legal_name?: string
  legal_form?: string
  registration_number?: string
  siren?: string
  siret?: string
  vat_number?: string
  naf_code?: string
  registration_date?: string
  registered_address?: Record<string, unknown>
  legal_representative_associate_id?: string
  objet_social?: string
  duree_societe?: number
  date_signature_statuts?: string
  // Lot 1 (24/09/2026, service 1.1.4) : lus automatiquement par les statuts
  // (Art. 2, 3, 6, 7 et clôture) -- voir StatutsRedactionFields.tsx.
  // Montants en chaîne : le backend (Decimal) les sérialise ainsi.
  sigle?: string
  raison_d_etre?: string
  objectifs_ess?: string
  lieu_signature_statuts?: string
  capital_social?: string
  nombre_actions?: number
  valeur_nominale?: string
  lieu_immatriculation?: string
}

export interface ProjectLegalProfileRead extends ProjectLegalProfileCreate {
  id: string
  project_id: string
  kbis_document_id: string | null
  denomination_verification_status: string
  immatriculation_verification_status: string
  kbis_verification_status: string
  numero_suivi_formalite: string | null
  created_at: string
  updated_at: string
}

export interface ProjectPublicProfileUpdate {
  public_name?: string
  public_summary?: string
  sector?: string
  technologies?: string[]
  website_url?: string
  logo_url?: string
  funding_visibility?: ProjectVisibility
  compliance_visibility?: ProjectVisibility
  resolved_field_values?: FieldValueResolution[]
}

export interface ProjectPublicProfileRead extends ProjectPublicProfileUpdate {
  id: string
  project_id: string
  published_at: string | null
  updated_at: string
}

// ---------------------------------------------------------------------------
// Équipe & capital — `project_associates` (socle Groupe 5, 1.1.4/1.1.6/1.1.13)
// ---------------------------------------------------------------------------

export type AssociateTypePersonne = "personne_physique" | "personne_morale"
export type AssociateTypeApport = "numeraire" | "nature" | "industrie"

/** Un associé du projet (capital + droits de vote). Reflète ProjectAssociateRead
 * côté backend — voir associate_service.py pour les règles bloquantes :
 * somme des parts = 100 %, ≥1 dirigeant, apport en industrie exclu du capital.
 * `linked_user_id` n'est PAS éditable côté frontend (associé = propriétaire,
 * auto-rempli par le backend). (réalisé par OPENCODE) */
export interface ProjectAssociateRead {
  id: string
  project_id: string
  nom_complet: string
  type_personne: AssociateTypePersonne
  date_naissance: string | null
  lieu_naissance: string | null
  /** Imprimée dans l'en-tête des statuts (personne physique). */
  situation_et_regime_matrimonial: string | null
  nationalite: string | null
  adresse: string | null
  pourcentage_capital: string
  pourcentage_droits_vote: string | null
  type_apport: AssociateTypeApport
  /** Désignation du bien apporté (si type_apport === "nature") — lue par les statuts (Art. 6). */
  description_apport_nature: string | null
  est_dirigeant: boolean
  fonction_dirigeant: string | null
  foyer_fiscal_dirigeant_associate_id: string | null
  est_partie_au_pacte_fondateurs: boolean
  /** Ajout migration c8f4d1a6b2e9 (service 1.1.13) — distingue Associés
   * Fondateurs / Associés Investisseurs pour le préambule du pacte. */
  est_fondateur: boolean
  /** Ajout migration b2c4d6e8f0a2 (service 1.1.13) — pertinents seulement si
   * `type_personne === "personne_morale"`. Manquaient du schéma Pydantic
   * jusqu'au 24/09/2026 (colonnes en base mais jamais exposées par l'API). */
  denomination_sociale: string | null
  type_societe: string | null
  capital_social: string | null
  siege_social: string | null
  lieu_immatriculation: string | null
  numero_siren: string | null
  representant_nom: string | null
  representant_prenom: string | null
  representant_qualite: string | null
  linked_user_id: string | null
  created_at: string
  updated_at: string
}

/** Élément du PUT /projects/{id}/associates (Enregistrer globant) — la liste
 * COMPLÈTE est envoyée au clic "Enregistrer". `id` présent = mise à jour d'une
 * ligne existante, absent = création. Le backend valide l'état cible avant
 * d'écrire : somme des parts = 100 %, ≥1 dirigeant, foyer fiscal (rattachement
 * d'un associé au foyer fiscal d'un dirigeant, art. 239 bis AB CGI). */
export interface ProjectAssociateBatchItem {
  id?: string | null
  nom_complet: string
  type_personne: AssociateTypePersonne
  date_naissance?: string | null
  lieu_naissance?: string | null
  situation_et_regime_matrimonial?: string | null
  nationalite?: string | null
  adresse?: string | null
  pourcentage_capital: string
  pourcentage_droits_vote?: string | null
  type_apport: AssociateTypeApport
  description_apport_nature?: string | null
  est_dirigeant: boolean
  fonction_dirigeant?: string | null
  foyer_fiscal_dirigeant_associate_id?: string | null
  est_partie_au_pacte_fondateurs: boolean
  est_fondateur: boolean
  denomination_sociale?: string | null
  type_societe?: string | null
  capital_social?: string | null
  siege_social?: string | null
  lieu_immatriculation?: string | null
  numero_siren?: string | null
  representant_nom?: string | null
  representant_prenom?: string | null
  representant_qualite?: string | null
}

/** Dirigeants désignés dans les statuts (`company_officers`, service 1.1.4,
 * lot 5) — Président, 1er Directeur Général, membres du comité, mandataire
 * pour les actes avant immatriculation (art. 39-41, 44). */
export type RoleDirigeant = "president" | "directeur_general" | "membre_comite" | "mandataire"

interface CompanyOfficerFields {
  role: RoleDirigeant
  /** Renseigné si le dirigeant est un associé : son identité vient alors de
   * "Équipe & capital" et les champs d'identité ci-dessous restent vides. */
  associate_id: string | null
  type_personne: AssociateTypePersonne
  duree_fonctions: string | null
  nom_complet: string | null
  denomination_sociale: string | null
  forme_juridique: string | null
  capital_social: string | null
  siege_social: string | null
  lieu_immatriculation: string | null
  siren: string | null
  representant_nom: string | null
  representant_prenom: string | null
  adresse: string | null
}

export interface CompanyOfficerRead extends CompanyOfficerFields {
  id: string
  project_id: string
  created_at: string
  updated_at: string
}

/** Corps de POST /officers et PATCH /officers/{id} — un dirigeant à la fois. */
export type CompanyOfficerWrite = CompanyOfficerFields

export type ExtractionSource = "extrait_automatique" | "saisi_par_utilisateur"
export type ValidationStatus = "en_attente" | "confirme" | "corrige"

/** `field_name` porte un préfixe "table.colonne" (ex: "projects.sector") pour
 * lever l'ambiguïté entre tables qui partagent un nom de champ — voir
 * document_service.py côté backend. */
export interface ProjectFieldValueRead {
  id: string
  project_id: string
  field_name: string
  field_value: string | null
  extraction_source: ExtractionSource
  validation_status: ValidationStatus
  created_at: string
  updated_at: string
}

export interface ProjectFieldValueUpdate {
  /** Nouvelle valeur si l'utilisateur corrige — doit être encodée en JSON
   * (JSON.stringify), même pour du texte simple. Omis = on garde la valeur déjà
   * extraite (cas "confirmer"). */
  field_value?: string
  validation_status: "confirme" | "corrige"
}

/** `field_value` est toujours du JSON côté backend (voir document_service.py) —
 * même un texte simple est stocké entre guillemets. À utiliser pour tout
 * affichage ou pré-remplissage d'un champ extrait. */
export function parseFieldValue(raw: string | null): unknown {
  if (raw === null) return null
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

async function request<T>(
  accessToken: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = parseErrorDetail(body.detail, detail)
    } catch {
      // Réponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function createProject(
  accessToken: string,
  data: { project_type: ProjectType; stage: ProjectStage },
): Promise<ProjectRead> {
  return request<ProjectRead>(accessToken, "/projects", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

/** Retourne `null` si l'entrepreneur n'a pas encore de projet — état normal juste
 * après signup, utilisé pour décider wizard vs accueil (voir App.tsx). */
export function getMyProject(accessToken: string): Promise<ProjectRead | null> {
  return request<ProjectRead | null>(accessToken, "/projects/me")
}

export function getProject(
  accessToken: string,
  projectId: string,
): Promise<ProjectRead> {
  return request<ProjectRead>(accessToken, `/projects/${projectId}`)
}

export function updateProject(
  accessToken: string,
  projectId: string,
  data: ProjectUpdate,
): Promise<ProjectRead> {
  return request<ProjectRead>(accessToken, `/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export function createLegalProfile(
  accessToken: string,
  projectId: string,
  data: ProjectLegalProfileCreate,
): Promise<ProjectLegalProfileRead> {
  return request<ProjectLegalProfileRead>(
    accessToken,
    `/projects/${projectId}/legal-profile`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  )
}

/** PATCH /projects/{id}/legal-profile — upsert, contrairement à createLegalProfile
 * (POST) qui échoue si un profil existe déjà. Sert au bouton "Mettre à jour" de
 * "Informations légales" (voir UpdateLegalProfileForm.tsx). */
export function updateLegalProfile(
  accessToken: string,
  projectId: string,
  data: ProjectLegalProfileUpdate,
): Promise<ProjectLegalProfileRead> {
  return request<ProjectLegalProfileRead>(
    accessToken,
    `/projects/${projectId}/legal-profile`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  )
}

/** POST /projects/{id}/legal-profile/verify — déclenche la vraie vérification
 * (appel à l'API Recherche d'Entreprises), séparée de updateLegalProfile (PATCH) :
 * sauvegarder ne doit jamais dépendre d'un service externe qui peut échouer ou
 * être lent. Appelée par UpdateLegalProfileForm.tsx juste après la sauvegarde,
 * uniquement pour Parcours B (project_type === "created"). */
export function verifyLegalProfile(
  accessToken: string,
  projectId: string,
): Promise<ProjectLegalProfileRead> {
  return request<ProjectLegalProfileRead>(
    accessToken,
    `/projects/${projectId}/legal-profile/verify`,
    { method: "POST" },
  )
}

/** Upload multipart — pas de Content-Type JSON ici, le navigateur pose lui-même
 * le boundary multipart/form-data quand le body est un FormData. */
export async function uploadProjectLogo(
  accessToken: string,
  projectId: string,
  file: File,
): Promise<{ logo_url: string }> {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/upload-logo`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData,
    },
  )

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = parseErrorDetail(body.detail, detail)
    } catch {
      // idem
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as { logo_url: string }
}

/** GET /projects/{id}/legal-profile — ajouté pour le dashboard "Mon projet"
 * (lecture seule) : `null` si l'écran 3 n'a pas encore été rempli, jamais une
 * erreur (voir get_legal_profile côté backend). */
export function getLegalProfile(
  accessToken: string,
  projectId: string,
): Promise<ProjectLegalProfileRead | null> {
  return request<ProjectLegalProfileRead | null>(
    accessToken,
    `/projects/${projectId}/legal-profile`,
  )
}

/** GET /projects/{id}/public-profile — même raisonnement que getLegalProfile :
 * `null` si l'écran 9 (facultatif) n'a jamais été soumis. */
export function getPublicProfile(
  accessToken: string,
  projectId: string,
): Promise<ProjectPublicProfileRead | null> {
  return request<ProjectPublicProfileRead | null>(
    accessToken,
    `/projects/${projectId}/public-profile`,
  )
}

export function upsertPublicProfile(
  accessToken: string,
  projectId: string,
  data: ProjectPublicProfileUpdate,
): Promise<ProjectPublicProfileRead> {
  return request<ProjectPublicProfileRead>(
    accessToken,
    `/projects/${projectId}/public-profile`,
    {
      method: "POST",
      body: JSON.stringify(data),
    },
  )
}

/** Upload multipart — même remarque que uploadProjectLogo : pas de Content-Type
 * JSON, le navigateur pose le boundary lui-même. Peut prendre plusieurs
 * secondes (VLM + 3 appels LLM côté backend), à refléter dans l'UI appelante. */
export async function uploadDocument(
  accessToken: string,
  projectId: string,
  file: File,
): Promise<ProjectFieldValueRead[]> {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/upload-document`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
      body: formData,
    },
  )

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = parseErrorDetail(body.detail, detail)
    } catch {
      // idem
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as ProjectFieldValueRead[]
}

export function getFieldValues(
  accessToken: string,
  projectId: string,
): Promise<ProjectFieldValueRead[]> {
  return request<ProjectFieldValueRead[]>(
    accessToken,
    `/projects/${projectId}/field-values`,
  )
}

export function resolveFieldValue(
  accessToken: string,
  projectId: string,
  fieldValueId: string,
  data: ProjectFieldValueUpdate,
): Promise<ProjectFieldValueRead> {
  return request<ProjectFieldValueRead>(
    accessToken,
    `/projects/${projectId}/field-values/${fieldValueId}`,
    {
      method: "PATCH",
      body: JSON.stringify(data),
    },
  )
}

export function ignoreFieldValue(
  accessToken: string,
  projectId: string,
  fieldValueId: string,
): Promise<void> {
  return request<void>(
    accessToken,
    `/projects/${projectId}/field-values/${fieldValueId}`,
    { method: "DELETE" },
  )
}

// ---------------------------------------------------------------------------
// Équipe & capital
// ---------------------------------------------------------------------------

/** GET /projects/{id}/associates — le backend matérialise la ligne du fondateur
 * (associé = propriétaire, 100 % solo, dirigeant) si la page n'a jamais été ouverte. */
export function getAssociates(
  accessToken: string,
  projectId: string,
): Promise<ProjectAssociateRead[]> {
  return request<ProjectAssociateRead[]>(
    accessToken,
    `/projects/${projectId}/associates`,
  )
}

/** PUT /projects/{id}/associates — enregistrement GLOBAL de la page. La liste
 * complète (brouillon) est envoyée au clic "Enregistrer" ; `id` null = création,
 * présent = mise à jour. Règle bloquante (somme = 100 %, ≥1 dirigeant) validée
 * par le backend avant écriture. Renvoie l'état persisté à recharger. */
export function replaceAssociates(
  accessToken: string,
  projectId: string,
  items: ProjectAssociateBatchItem[],
): Promise<ProjectAssociateRead[]> {
  return request<ProjectAssociateRead[]>(
    accessToken,
    `/projects/${projectId}/associates`,
    { method: "PUT", body: JSON.stringify(items) },
  )
}

/** PATCH /projects/{id}/associates/{associate_id} — mise à jour partielle
 * (backend : `ProjectAssociateUpdate`, `exclude_unset=True`, aucune des règles
 * de blocage de `replaceAssociates` ne s'applique à un champ non envoyé).
 * Utilisée pour le seul champ `est_fondateur` par l'écran de sélection des
 * fondateurs du pacte v2 (`PacteFoundersSelectionV2`) — plus léger que
 * `replaceAssociates`, qui exigerait de renvoyer l'état complet de tous les
 * associés (capital, dirigeant...) juste pour basculer un booléen. */
export function updateAssociateFondateur(
  accessToken: string,
  projectId: string,
  associateId: string,
  estFondateur: boolean,
): Promise<ProjectAssociateRead> {
  return request<ProjectAssociateRead>(
    accessToken,
    `/projects/${projectId}/associates/${associateId}`,
    { method: "PATCH", body: JSON.stringify({ est_fondateur: estFondateur }) },
  )
}

export function getOfficers(accessToken: string, projectId: string): Promise<CompanyOfficerRead[]> {
  return request<CompanyOfficerRead[]>(accessToken, `/projects/${projectId}/officers`)
}

/** Une action = un enregistrement (page Dirigeants). Refusé (400) si un 2e
 * Président, DG ou mandataire est ajouté, ou si l'identité manque. */
export function createOfficer(
  accessToken: string,
  projectId: string,
  data: CompanyOfficerWrite,
): Promise<CompanyOfficerRead> {
  return request<CompanyOfficerRead>(accessToken, `/projects/${projectId}/officers`, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export function updateOfficer(
  accessToken: string,
  projectId: string,
  officerId: string,
  data: CompanyOfficerWrite,
): Promise<CompanyOfficerRead> {
  return request<CompanyOfficerRead>(accessToken, `/projects/${projectId}/officers/${officerId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export function deleteOfficer(accessToken: string, projectId: string, officerId: string): Promise<void> {
  return request<void>(accessToken, `/projects/${projectId}/officers/${officerId}`, { method: "DELETE" })
}
