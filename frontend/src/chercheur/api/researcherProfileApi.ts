/**
 * Client HTTP pour `backend/chercheur` (profil) — même pattern que
 * shared/api/authApi.ts : un fichier, une responsabilité, pas de state ici
 * (voir AuthContext pour les tokens). Réutilise la classe ApiError de
 * authApi.ts plutôt que d'en redéfinir une deuxième — un seul type d'erreur
 * HTTP dans toute l'app, pas un par domaine.
 */
import { ApiError } from "../../shared/api/authApi"
// Réutilise FieldValue plutôt que de redéfinir un type identique — même
// mécanisme polymorphe researcher_field_values des deux côtés (voir
// researcher_field_value_service.py).
import type { FieldValue } from "./researchWorkApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type SyncStatus = "not_started" | "queued" | "in_progress" | "completed" | "failed"
export type ProfileCompletion = "incomplet" | "complet"
export type ExtractionPreference = "extraire" | "deposer" | "les_deux"

export interface ResearcherProfileRead {
  id: string
  user_id: string
  orcid_id: string | null
  affiliation: string | null
  research_domains: string[]
  sync_status: SyncStatus
  last_synced_at: string | null
  expertise_summary: string | null
  research_work_summary: string | null
  profile_completion: ProfileCompletion
  created_at: string
  updated_at: string
  generated_field_values: FieldValue[]
}

export interface OnboardingRequest {
  affiliation: string
  extraction_preference: ExtractionPreference
  orcid_id?: string | null
  research_domains?: string[]
}

/** Body du PATCH /chercheur/profile — tous les champs optionnels, seuls ceux
 * envoyés sont modifiés côté backend (voir update_profile côté service). */
export interface ProfileUpdateRequest {
  orcid_id?: string | null
  affiliation?: string
  research_domains?: string[]
  expertise_summary?: string
  research_work_summary?: string
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
      // Réponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

export function getMyResearcherProfile(accessToken: string): Promise<ResearcherProfileRead> {
  return request<ResearcherProfileRead>("/chercheur/profile", accessToken)
}

export function completeOnboarding(accessToken: string, data: OnboardingRequest): Promise<ResearcherProfileRead> {
  return request<ResearcherProfileRead>("/chercheur/onboarding", accessToken, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export function updateResearcherProfile(
  accessToken: string,
  data: ProfileUpdateRequest,
): Promise<ResearcherProfileRead> {
  return request<ResearcherProfileRead>("/chercheur/profile", accessToken, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export function deleteExpertiseSummary(accessToken: string): Promise<ResearcherProfileRead> {
  return request<ResearcherProfileRead>("/chercheur/profile/expertise-summary", accessToken, {
    method: "DELETE",
  })
}

export function deleteResearchWorkSummary(accessToken: string): Promise<ResearcherProfileRead> {
  return request<ResearcherProfileRead>("/chercheur/profile/research-work-summary", accessToken, {
    method: "DELETE",
  })
}

/** Génère expertise_summary à partir de researcher_past_expertises (tâche de
 * fond, pas de corps de réponse exploitable — même pattern que triggerExtraction
 * côté researchWorkApi.ts). Rattrapable indépendamment de research_work_summary. */
export async function triggerExpertiseSummary(accessToken: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chercheur/profile/generer-expertise-summary`, {
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

/** Génère research_work_summary à partir des research_works du profil. */
export async function triggerResearchWorkSummary(accessToken: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/chercheur/profile/generer-research-work-summary`, {
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