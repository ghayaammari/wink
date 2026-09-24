/**
 * Client HTTP pour `backend/entrepreneur/routes/startup_offer_matching_
 * router.py` — service EPIC-06 (matching Startup -> Offres, sens inverse
 * de researchNeedApi.ts::runChercheurMatching). Vit dans
 * `frontend/src/entrepreneur/api/` comme le reste des écrans propres à
 * l'entrepreneur. Même convention que researchNeedApi.ts (réutilise
 * ApiError de authApi.ts).
 *
 * Contrairement au matching chercheur (un feed par "besoin" déclaré),
 * un projet n'a qu'UN SEUL feed d'offres -- pas de notion de besoin
 * intermédiaire à créer avant de lancer le matching.
 */
import { ApiError, parseErrorDetail } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type NiveauPertinence = "fort" | "moyen" | "faible"

export interface OfferMatch {
  offer_id: string
  rang: number
  niveau_pertinence: NiveauPertinence
  explication: string
  interesse: boolean
  // Champs de la fiche vivante de l'offre (ajoutés en lecture par
  // project_offer_match_service::_enrichir_matches) -- absents -> null
  // (offre supprimée depuis).
  titre: string | null
  montant_propose: number | null
  secteurs_cibles: string[] | null
  stades_cibles: string[] | null
  investor_type: string | null
  statut: string | null
}

export interface ProjectOfferMatchRead {
  id: string
  project_id: string
  matches: OfferMatch[]
  synthese: string
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
    let detail: string = response.statusText
    try {
      const body = await response.json()
      // parseErrorDetail (authApi.ts) : `detail` peut être un tableau
      // d'erreurs de validation Pydantic (422), jamais affichable tel quel
      // -- sans cette conversion, ApiError finissait affiché "[object
      // Object]" à l'écran (Error.toString() sur un non-string).
      detail = parseErrorDetail(body.detail, detail)
    } catch {
      // Réponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) {
    return null as T
  }
  const text = await response.text()
  return (text ? JSON.parse(text) : null) as T
}

// POST déclenche l'agent (coûteux, appel Groq), GET relit juste le dernier
// résultat persisté.

export function runOfferMatching(accessToken: string, projectId: string): Promise<ProjectOfferMatchRead> {
  return request<ProjectOfferMatchRead>(accessToken, `/projects/${projectId}/matching/offres`, { method: "POST" })
}

export function getOfferMatching(accessToken: string, projectId: string): Promise<ProjectOfferMatchRead | null> {
  return request<ProjectOfferMatchRead | null>(accessToken, `/projects/${projectId}/matching/offres`)
}

// Bascule le marquage "intéressé" d'une recommandation -- ce qui la fait
// apparaître (ou disparaître) de "Offres intéressantes" (voir
// listInterestingOffers).
export function toggleOfferInteret(
  accessToken: string,
  projectId: string,
  offerId: string,
  interesse: boolean,
): Promise<ProjectOfferMatchRead> {
  return request<ProjectOfferMatchRead>(accessToken, `/projects/${projectId}/matching/offres/${offerId}/interet`, {
    method: "PATCH",
    body: JSON.stringify({ interesse }),
  })
}

export function listInterestingOffers(accessToken: string, projectId: string): Promise<OfferMatch[]> {
  return request<OfferMatch[]>(accessToken, `/projects/${projectId}/matching/offres/interessantes`)
}
