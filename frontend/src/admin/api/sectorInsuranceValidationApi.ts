/**
 * Client HTTP pour le dashboard de validation humaine des recommandations
 * d'assurance sectorielles (service 1.1.10) — meme pattern que
 * legalTextsValidationApi.ts, fichier dedie (SRP).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ValidationAction = "valider" | "corriger"

export interface SectorInsuranceValidationItem {
  id: string
  secteur: string
  type_assurance: string
  a_base_legale: boolean
  source_nom: string | null
  source_url: string | null
  texte_brut: string | null
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
      // Reponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }

  return (await response.json()) as T
}

export function listPendingValidation(accessToken: string): Promise<SectorInsuranceValidationItem[]> {
  return request<SectorInsuranceValidationItem[]>(
    "/knowledge-base/sector-insurance/pending-validation",
    accessToken,
  )
}

export function submitValidation(
  accessToken: string,
  id: string,
  action: ValidationAction,
): Promise<SectorInsuranceValidationItem> {
  return request<SectorInsuranceValidationItem>(
    `/knowledge-base/sector-insurance/${id}/validation`,
    accessToken,
    {
      method: "PATCH",
      body: JSON.stringify({ action }),
    },
  )
}
