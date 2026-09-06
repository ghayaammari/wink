/**
 * Client HTTP pour `backend/chercheur/routes/researcher_past_expertise_router.py`
 * — même pattern que researchWorkApi.ts / researcherProfileApi.ts : un
 * fichier, une responsabilité, réutilise ApiError plutôt que d'en redéfinir
 * une deuxième.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface PastExpertise {
  id: string
  researcher_profile_id: string
  organization_name: string
  domain: string | null
  mission_type: string | null
  period_label: string | null
  description: string | null
  created_at: string
  updated_at: string
}

export interface PastExpertiseCreate {
  organization_name: string
  domain?: string | null
  mission_type?: string | null
  period_label?: string | null
  description?: string | null
}

export interface PastExpertiseUpdate {
  organization_name?: string
  domain?: string | null
  mission_type?: string | null
  period_label?: string | null
  description?: string | null
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

export function listPastExpertises(accessToken: string): Promise<PastExpertise[]> {
  return request<PastExpertise[]>("/chercheur/expertises", accessToken)
}

export function createPastExpertise(accessToken: string, data: PastExpertiseCreate): Promise<PastExpertise> {
  return request<PastExpertise>("/chercheur/expertises", accessToken, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export function updatePastExpertise(
  accessToken: string,
  expertiseId: string,
  data: PastExpertiseUpdate,
): Promise<PastExpertise> {
  return request<PastExpertise>(`/chercheur/expertises/${expertiseId}`, accessToken, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}