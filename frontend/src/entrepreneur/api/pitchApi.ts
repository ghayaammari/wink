/**
 * Client HTTP pour `backend/entrepreneur/routes/pitch_router.py` — service
 * 6.6.2 (generateur de pitch deck). Meme convention que aiActApi.ts :
 * accessToken en premier parametre, `request<T>` propre a ce fichier.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface ProjectPitchProfileRead {
  id: string
  project_id: string
  probleme: string | null
  solution: string | null
  marche: string | null
  modele_economique: string | null
  concurrence: string | null
  traction: string | null
  financements: string | null
  roadmap: string | null
  demande_investissement: string | null
  updated_at: string
}

export type ProjectPitchProfilePatch = Partial<
  Pick<
    ProjectPitchProfileRead,
    | "probleme"
    | "solution"
    | "marche"
    | "modele_economique"
    | "concurrence"
    | "traction"
    | "financements"
    | "roadmap"
    | "demande_investissement"
  >
>

// Miroir de agents/pitch_deck_agent/deck_schema.py (DeckContentModel) --
// seuls les champs affiches par PitchDeckPage.tsx sont types en detail, le
// reste (market.stat/highlight, team.members...) suit la meme forme cote
// backend mais n'a pas besoin d'un type dedie ici tant que l'UI ne les
// affiche pas individuellement (voir PitchDeckPage.tsx pour le rendu reel).
export interface PitchSlideWithBullets {
  title: string
  bullets: string[]
}

export interface PitchTeamMember {
  name: string
  role: string
  photo_url: string | null
}

export interface PitchDeckContent {
  project_id: string
  generated_at: string
  brand: { accent_color: string; logo_url: string | null }
  slides: {
    title: { startup_name: string; one_liner: string }
    problem: PitchSlideWithBullets
    solution: PitchSlideWithBullets
    market: PitchSlideWithBullets & {
      stat: { value: string; label: string } | null
      highlight: { value: string; label: string } | null
    }
    business_model: PitchSlideWithBullets
    competition: PitchSlideWithBullets
    traction: {
      title: string
      metrics: { label: string; value: string }[]
      milestones: { date: string; label: string }[]
    }
    team: { title: string; members: PitchTeamMember[] }
    financials: PitchSlideWithBullets
    roadmap: PitchSlideWithBullets
    cta: PitchSlideWithBullets & { ask_summary: string }
  }
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
      // Reponse sans corps JSON exploitable -- on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export function getPitchProfile(accessToken: string, projectId: string): Promise<ProjectPitchProfileRead> {
  return request(accessToken, `/projects/${projectId}/pitch/profile`)
}

export function updatePitchProfile(
  accessToken: string,
  projectId: string,
  data: ProjectPitchProfilePatch,
): Promise<ProjectPitchProfileRead> {
  return request(accessToken, `/projects/${projectId}/pitch/profile`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export function generatePitchDeck(accessToken: string, projectId: string): Promise<PitchDeckContent> {
  return request(accessToken, `/projects/${projectId}/pitch/generate`, { method: "POST" })
}

export async function getPitchDeck(accessToken: string, projectId: string): Promise<PitchDeckContent | null> {
  try {
    return await request(accessToken, `/projects/${projectId}/pitch`)
  } catch (err) {
    // 404 = aucun deck genere pour l'instant -- etat normal (pas une erreur a
    // remonter), voir PitchDeckPage.tsx.
    if (err instanceof ApiError && err.status === 404) return null
    throw err
  }
}

export async function downloadPitchDeckFile(accessToken: string, projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/pitch/file`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "pitch-deck.pptx"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
