/**
 * Client HTTP pour `backend/entrepreneur/routes/roadmap_router.py` — Plan
 * d'action pré-création (suivi de progression + preuve documentaire, V1).
 * Même convention que `projectApi.ts` : accessToken en premier paramètre.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// "verrouille" volontairement absent de RoadmapItemSettableStatut : c'est le
// backend (roadmap_service._cascade_unlock) qui le pose/le lève, jamais une
// action utilisateur directe.
export type RoadmapItemStatut = "verrouille" | "a_faire" | "en_cours" | "termine" | "non_necessaire"
export type RoadmapItemSettableStatut = Exclude<RoadmapItemStatut, "verrouille">

/** Copie figée du contenu du nœud au moment de l'assignation — voir
 * `node_snapshot` côté backend. Ne contient jamais `groupe`/`ordre` (lus en
 * live, voir RoadmapItemRead). */
export interface RoadmapNodeSnapshot {
  id: string
  nom: string
  input: string | null
  description: string
  details_pratiques: string | null
  administration_liee: string | null
  source_legale: string | null
  bloquant: boolean
}

export interface RoadmapItemRead {
  id: string
  project_id: string
  node_id: string
  groupe: string
  ordre: number
  statut: RoadmapItemStatut
  node_snapshot: RoadmapNodeSnapshot
  // Prérequis directs (ids de nœuds), exposés en live par le backend — voir
  // roadmap_service._dependencies_map. Jamais figé dans node_snapshot.
  depends_on: string[]
  proof_document_id: string | null
  proof_document_url: string | null
  assigned_at: string
  completed_at: string | null
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
  return (await response.json()) as T
}

export function getRoadmap(accessToken: string, projectId: string): Promise<RoadmapItemRead[]> {
  return request<RoadmapItemRead[]>(accessToken, `/projects/${projectId}/roadmap`)
}

export function updateRoadmapItemStatut(
  accessToken: string,
  projectId: string,
  nodeId: string,
  statut: RoadmapItemSettableStatut,
): Promise<RoadmapItemRead> {
  return request<RoadmapItemRead>(accessToken, `/projects/${projectId}/roadmap/${nodeId}`, {
    method: "PATCH",
    body: JSON.stringify({ statut }),
  })
}

/** Upload multipart — pas de Content-Type JSON, le navigateur pose lui-même
 * le boundary (même remarque que uploadProjectLogo/uploadDocument). */
export async function uploadRoadmapProof(
  accessToken: string,
  projectId: string,
  nodeId: string,
  file: File,
): Promise<RoadmapItemRead> {
  const formData = new FormData()
  formData.append("file", file)

  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/roadmap/${nodeId}/proof`,
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
  return (await response.json()) as RoadmapItemRead
}
