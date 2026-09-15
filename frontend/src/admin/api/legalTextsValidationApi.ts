/**
 * Client HTTP pour le dashboard de validation humaine des `legal_texts`
 * (Phase 1.5, service 1.1.1) — même pattern que investorProfileApi.ts :
 * réutilise ApiError de authApi.ts, pas de state ici.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ChunkingSuggere = "aucun" | "par_alinea"
export type ValidationAction = "valider" | "corriger"

export interface LegalTextValidationItem {
  id: string
  article_numero: string | null
  forme_juridique_concernee: string[]
  texte_brut: string
  chunking_suggere: ChunkingSuggere
  longueur_caracteres: number
  nb_alineas_detectes: number
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

export function listPendingValidation(accessToken: string): Promise<LegalTextValidationItem[]> {
  return request<LegalTextValidationItem[]>("/knowledge-base/legal-texts/pending-validation", accessToken)
}

export function submitValidation(
  accessToken: string,
  id: string,
  action: ValidationAction,
): Promise<LegalTextValidationItem> {
  return request<LegalTextValidationItem>(`/knowledge-base/legal-texts/${id}/validation`, accessToken, {
    method: "PATCH",
    body: JSON.stringify({ action }),
  })
}
