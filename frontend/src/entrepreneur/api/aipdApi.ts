/**
 * Client HTTP pour `backend/entrepreneur/routes/aipd_router.py` — service
 * 3.3.4 (AIPD). Fichier distinct de rgpdApi.ts (même raison que côté
 * backend : responsabilité différente, voir docstring de aipd_router.py).
 * Même convention que rgpdApi.ts : `request<T>` propre à ce fichier.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface AipdAnalysisRead {
  id: string
  project_id: string
  project_rgpd_obligation_id: string | null
  contenu: string
  generated_at: string
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

export function getAipdAnalyses(accessToken: string, projectId: string): Promise<AipdAnalysisRead[]> {
  return request<AipdAnalysisRead[]>(accessToken, `/projects/${projectId}/rgpd/aipd`)
}

// Appel potentiellement long (recherche vectorielle + génération LLM) — voir
// AipdAnalysisPage pour l'état de chargement associé.
export function generateAipdAnalysis(accessToken: string, projectId: string): Promise<AipdAnalysisRead> {
  return request<AipdAnalysisRead>(accessToken, `/projects/${projectId}/rgpd/aipd`, { method: "POST" })
}
