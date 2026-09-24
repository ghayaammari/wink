/**
 * Client HTTP pour `backend/entrepreneur/routes/investment_offer_catalogue_
 * router.py` — lecture brute de TOUTES les offres d'investissement
 * ouvertes, sans scoring ni agent. Fichier séparé de offerMatchingApi.ts :
 * ici pas de project_id, pas d'agent, juste un catalogue public en lecture
 * seule (l'entrepreneur doit pouvoir parcourir toutes les offres avant de
 * lancer le matching, pas seulement celles que l'agent recommande).
 */
import { ApiError, parseErrorDetail } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface OfferCatalogueItem {
  id: string
  titre: string
  description: string
  montant_propose: number
  secteurs_cibles: string[]
  stades_cibles: string[]
  investor_type: string | null
  created_at: string
}

export async function listOfferCatalogue(accessToken: string): Promise<OfferCatalogueItem[]> {
  const response = await fetch(`${API_BASE_URL}/investissement/offres`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    let detail: string = response.statusText
    try {
      const body = await response.json()
      detail = parseErrorDetail(body.detail, detail)
    } catch {
      // Réponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }
  return response.json()
}
