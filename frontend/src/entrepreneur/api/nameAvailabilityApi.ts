/**
 * Client HTTP pour `backend/entrepreneur/routes/name_availability_router.py` —
 * service 1.1.2 (vérificateur croisé de disponibilité du nom). Même convention
 * que roadmapApi.ts : accessToken en premier paramètre.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type StatutDenomination = "disponible" | "pris"
export type StatutMarque = "disponible" | "risque" | "pris"

export interface NameAvailabilityCheckRead {
  id: string
  project_id: string
  nom_teste: string
  statut_denomination: StatutDenomination
  statut_marque: StatutMarque
  verifie_le: string
}

async function request<T>(accessToken: string, path: string, options: RequestInit = {}): Promise<T> {
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

export function checkNameAvailability(
  accessToken: string,
  projectId: string,
  nomTeste: string,
): Promise<NameAvailabilityCheckRead> {
  return request<NameAvailabilityCheckRead>(accessToken, `/projects/${projectId}/name-availability-checks`, {
    method: "POST",
    body: JSON.stringify({ nom_teste: nomTeste }),
  })
}

export function getNameAvailabilityHistory(
  accessToken: string,
  projectId: string,
): Promise<NameAvailabilityCheckRead[]> {
  return request<NameAvailabilityCheckRead[]>(accessToken, `/projects/${projectId}/name-availability-checks`)
}
