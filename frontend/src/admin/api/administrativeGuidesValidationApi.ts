/**
 * Client HTTP pour le dashboard de validation humaine des `administrative_guides`
 * (agent réglementaire, Incrément 1) — même pattern que legalTextsValidationApi.ts.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface AdministrativeGuideValidationItem {
  id: string
  domaine: string
  source_nom: string
  source_url: string
  titre: string | null
  texte_brut: string
  longueur_caracteres: number
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

export function listPendingValidation(accessToken: string): Promise<AdministrativeGuideValidationItem[]> {
  return request<AdministrativeGuideValidationItem[]>(
    "/knowledge-base/administrative-guides/pending-validation",
    accessToken,
  )
}

export function submitValidation(
  accessToken: string,
  id: string,
): Promise<AdministrativeGuideValidationItem> {
  return request<AdministrativeGuideValidationItem>(
    `/knowledge-base/administrative-guides/${id}/validation`,
    accessToken,
    { method: "PATCH" },
  )
}
