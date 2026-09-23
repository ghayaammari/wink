/**
 * Client HTTP pour `backend/matching/routes/research_need_router.py` —
 * service 7.7.1 (dépôt de besoin scientifique, côté entrepreneur). Vit dans
 * `frontend/src/entrepreneur/api/` et non un dossier `matching/` séparé :
 * l'écran de dépôt est propre à l'entrepreneur (voir Wink_architecture_fichiers.md
 * — pas de dossier frontend cross-acteurs, chaque acteur a ses propres écrans
 * même pour une fonctionnalité dont le backend est cross-acteurs). Même
 * convention que certificationApi.ts : réutilise ApiError de authApi.ts.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type TypeBesoin = "probleme" | "expertise"
export type StatutBesoin = "ouvert" | "ferme"

export interface ResearchNeedRead {
  id: string
  project_id: string
  type_besoin: TypeBesoin
  titre: string
  description: string
  statut: StatutBesoin
  created_at: string
  updated_at: string
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

export function listResearchNeeds(accessToken: string, projectId: string): Promise<ResearchNeedRead[]> {
  return request<ResearchNeedRead[]>(accessToken, `/projects/${projectId}/matching/research-needs`)
}

export function createResearchNeed(
  accessToken: string,
  projectId: string,
  typeBesoin: TypeBesoin,
  titre: string,
  description: string,
): Promise<ResearchNeedRead> {
  return request<ResearchNeedRead>(accessToken, `/projects/${projectId}/matching/research-needs`, {
    method: "POST",
    body: JSON.stringify({ type_besoin: typeBesoin, titre, description }),
  })
}

export function updateResearchNeedStatut(
  accessToken: string,
  projectId: string,
  needId: string,
  statut: StatutBesoin,
): Promise<ResearchNeedRead> {
  return request<ResearchNeedRead>(accessToken, `/projects/${projectId}/matching/research-needs/${needId}`, {
    method: "PATCH",
    body: JSON.stringify({ statut }),
  })
}

// --- Matching chercheurs (service 7.7.2, agents/matching_agent/chercheur_matching_service.py) ---
// Deux endpoints distincts de research-needs ci-dessus : POST declenche
// l'agent (couteux, appel Groq), GET relit juste le dernier resultat
// persiste (backend/matching/routes/chercheur_matching_router.py).

export type NiveauPertinence = "fort" | "moyen" | "faible"

export interface ChercheurMatch {
  researcher_profile_id: string
  nom: string
  rang: number
  niveau_pertinence: NiveauPertinence
  explication: string
  interesse: boolean
}

export interface ResearchNeedMatchRead {
  id: string
  research_need_id: string
  matches: ChercheurMatch[]
  synthese: string
  created_at: string
  updated_at: string
}

export interface RecommandationInteressante {
  need_id: string
  need_titre: string
  match: ChercheurMatch
}

export function runChercheurMatching(
  accessToken: string,
  projectId: string,
  needId: string,
): Promise<ResearchNeedMatchRead> {
  return request<ResearchNeedMatchRead>(
    accessToken,
    `/projects/${projectId}/matching/research-needs/${needId}/chercheurs`,
    { method: "POST" },
  )
}

export function getChercheurMatching(
  accessToken: string,
  projectId: string,
  needId: string,
): Promise<ResearchNeedMatchRead | null> {
  return request<ResearchNeedMatchRead | null>(
    accessToken,
    `/projects/${projectId}/matching/research-needs/${needId}/chercheurs`,
  )
}

// Bascule le marquage "intéressé" d'une recommandation -- ce qui la fait
// apparaître (ou disparaître) de la sous-partie "Recommandations
// intéressantes" du sidebar (voir listRecommandationsInteressantes).
export function toggleChercheurInteret(
  accessToken: string,
  projectId: string,
  needId: string,
  researcherProfileId: string,
  interesse: boolean,
): Promise<ResearchNeedMatchRead> {
  return request<ResearchNeedMatchRead>(
    accessToken,
    `/projects/${projectId}/matching/research-needs/${needId}/chercheurs/${researcherProfileId}/interet`,
    { method: "PATCH", body: JSON.stringify({ interesse }) },
  )
}

// Vue transversale (tous les besoins du projet) des recommandations
// marquées "intéressé" -- alimente la page "Recommandations intéressantes".
export function listRecommandationsInteressantes(
  accessToken: string,
  projectId: string,
): Promise<RecommandationInteressante[]> {
  return request<RecommandationInteressante[]>(
    accessToken,
    `/projects/${projectId}/matching/recommandations-interessantes`,
  )
}
