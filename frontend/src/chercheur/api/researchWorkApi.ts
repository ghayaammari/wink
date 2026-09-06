import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ValidationStatus = "pending_confirmation" | "confirmed" | "rejected" | "superseded"
export type WorkValidationStatus = "pending_confirmation" | "confirmed" | "rejected"
export type Visibility = "public_profile" | "private_matching_only"
export type SourceType = "extrait_hal_openalex" | "depot_manuel"
export type PublicationType = "article" | "communication" | "these" | "brevet" | "rapport"

export interface FieldValue {
  id: string
  entity_type: "researcher_profile" | "research_work"
  entity_id: string
  field_name: string
  field_value: string
  source: "extracted_from_papers" | "user_added" | "llm_generated" | "llm_analysis"
  validation_status: ValidationStatus
  created_at: string
  updated_at: string
}

export interface ResearchWork {
  id: string
  researcher_profile_id: string
  title: string
  abstract: string | null
  authors: string[] | null
  venue: string | null
  doi: string | null
  external_url: string | null
  publication_type: PublicationType | null
  source_type: SourceType
  file_url: string | null
  validation_status: WorkValidationStatus
  visibility: Visibility
  created_at: string
  updated_at: string
  generated_field_values: FieldValue[]
}

export interface WorkUpdate {
  title?: string
  abstract?: string | null
  authors?: string[] | null
  venue?: string | null
  doi?: string | null
  publication_type?: PublicationType | null
}

async function request<T>(path: string, accessToken: string, options: RequestInit = {}): Promise<T> {
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
      // pas de corps JSON exploitable
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

/** Dépôt = juste le fichier. Réponse 202 sans research_work — le job tourne
 * en fond, voir listMyWorks() + polling côté page pour détecter l'apparition
 * du nouveau travail. */
export async function depositWork(accessToken: string, file: File): Promise<void> {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch(`${API_BASE_URL}/chercheur/travaux/depot`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
    body: formData,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // pas de corps JSON exploitable
    }
    throw new ApiError(response.status, detail)
  }
}

export function listMyWorks(accessToken: string): Promise<ResearchWork[]> {
  return request<ResearchWork[]>("/chercheur/travaux", accessToken)
}

/** Déclenche l'extraction HAL/OpenAlex à la demande (bouton "Extraire" —
 * plus de lancement automatique à l'onboarding). Peut créer plusieurs
 * ResearchWork ; pas de corps de réponse exploitable, même pattern que
 * depositWork() : le frontend détecte la fin par polling de listMyWorks(). */
export async function triggerExtraction(accessToken: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chercheur/travaux/extraire`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // pas de corps JSON exploitable
    }
    throw new ApiError(response.status, detail)
  }
}

/** Rattrapage manuel quand un travail n'a aucun champ généré (échec LLM
 * initial, typiquement un rate limit Groq — voir research_extraction_service).
 * Tâche de fond côté backend, pas de valeur de retour à attendre ici. */
export async function regenerateAnalysis(accessToken: string, workId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chercheur/travaux/${workId}/regenerer-analyse`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // pas de corps JSON exploitable
    }
    throw new ApiError(response.status, detail)
  }
}

export function updateWork(accessToken: string, workId: string, data: WorkUpdate): Promise<ResearchWork> {
  return request<ResearchWork>(`/chercheur/travaux/${workId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export function validateField(
  accessToken: string,
  fieldValueId: string,
  action: "confirm" | "reject" | "edit",
  newValue?: string,
): Promise<FieldValue> {
  return request<FieldValue>(`/chercheur/travaux/champs/${fieldValueId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(action === "edit" ? { action, new_value: newValue } : { action }),
  })
}

export async function deleteWork(accessToken: string, workId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chercheur/travaux/${workId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // 204 No Content en cas de succès, ou erreur sans corps JSON
    }
    throw new ApiError(response.status, detail)
  }
}