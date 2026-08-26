/**
 * Client HTTP pour `backend/entrepreneur/routes/project_router.py` — un fichier,
 * une responsabilité : parler à l'API `/projects`, rien d'autre (pas de state,
 * voir `entrepreneur/context/OnboardingWizardContext.tsx` pour ça).
 *
 * Toutes les routes sont protégées côté backend (Depends(get_current_user)), donc
 * chaque fonction ici prend l'access token en premier paramètre — même convention
 * que `getCurrentUser` dans `shared/api/authApi.ts`.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ProjectType = "not_created" | "created"
export type ProjectStage = "ideation" | "pre_seed" | "seed" | "serie_a"
export type ProjectSourceType = "texte_libre" | "document_importe"
export type ProjectProfileCompletion = "incomplet" | "complet"

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
  intention_levee_fonds?: boolean
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
  is_registered?: boolean
  legal_name?: string
  legal_form?: string
  registration_number?: string
  siren?: string
  siret?: string
  vat_number?: string
  naf_code?: string
  registration_date?: string
  registered_address?: Record<string, unknown>
  legal_representative?: Record<string, unknown>
}

export interface ProjectLegalProfileRead extends ProjectLegalProfileCreate {
  id: string
  project_id: string
  is_registered: boolean
  verification_status: string
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
  funding_visibility?: string
  compliance_visibility?: string
  resolved_field_values?: FieldValueResolution[]
}

export interface ProjectPublicProfileRead extends ProjectPublicProfileUpdate {
  id: string
  project_id: string
  published_at: string | null
  updated_at: string
}

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
      detail = body.detail ?? detail
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
      detail = body.detail ?? detail
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
      detail = body.detail ?? detail
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
