/**
 * Client HTTP pour `backend/investisseur/routes/investment_offer_router.py`
 * et `investisseur_matching_router.py` (EPIC-07, volet Investisseur ->
 * Startup du matching). Même convention que researchNeedApi.ts côté
 * entrepreneur : réutilise ApiError de authApi.ts.
 */
import { ApiError, parseErrorDetail } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type StatutOffre = "ouvert" | "ferme"

export interface InvestmentOfferRead {
  id: string
  investor_profile_id: string
  titre: string
  description: string
  montant_propose: number
  secteurs_cibles: string[]
  stades_cibles: string[]
  statut: StatutOffre
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
  return (await response.json()) as T
}

export function listInvestmentOffers(accessToken: string): Promise<InvestmentOfferRead[]> {
  return request<InvestmentOfferRead[]>(accessToken, "/investisseur/offres")
}

export function getInvestmentOffer(accessToken: string, offerId: string): Promise<InvestmentOfferRead> {
  return request<InvestmentOfferRead>(accessToken, `/investisseur/offres/${offerId}`)
}

export function createInvestmentOffer(
  accessToken: string,
  titre: string,
  description: string,
  montantPropose: number,
  secteursCibles: string[],
  stadesCibles: string[],
): Promise<InvestmentOfferRead> {
  return request<InvestmentOfferRead>(accessToken, "/investisseur/offres", {
    method: "POST",
    body: JSON.stringify({
      titre,
      description,
      montant_propose: montantPropose,
      secteurs_cibles: secteursCibles,
      stades_cibles: stadesCibles,
    }),
  })
}

export function updateInvestmentOfferStatut(
  accessToken: string,
  offerId: string,
  statut: StatutOffre,
): Promise<InvestmentOfferRead> {
  return request<InvestmentOfferRead>(accessToken, `/investisseur/offres/${offerId}`, {
    method: "PATCH",
    body: JSON.stringify({ statut }),
  })
}

// --- Matching startups (service EPIC-07, agents/matching_agent/investisseur_matching_service.py) ---
// POST declenche l'agent (couteux, appel Groq), GET relit juste le dernier
// resultat persiste.

export type NiveauPertinence = "fort" | "moyen" | "faible"

export interface StartupMatch {
  project_id: string
  nom: string
  rang: number
  niveau_pertinence: NiveauPertinence
  explication: string
  interesse: boolean
  // Champs de la fiche vivante du projet (Project/ProjectPublicProfile),
  // ajoutés en lecture par investment_offer_match_service::_enrichir_matches
  // -- jamais écrits par l'agent. Absents -> null (projet supprimé, ou
  // vitrine publique jamais renseignée).
  secteur: string | null
  stade: string | null
  localisation: string | null
  value_proposition: string | null
  technologies: string[] | null
  logo_url: string | null
  website_url: string | null
}

export interface InvestmentOfferMatchRead {
  id: string
  investment_offer_id: string
  matches: StartupMatch[]
  synthese: string
  created_at: string
  updated_at: string
}

export interface StartupInteressante {
  offer_id: string
  offer_titre: string
  match: StartupMatch
}

export function runStartupMatching(accessToken: string, offerId: string): Promise<InvestmentOfferMatchRead> {
  return request<InvestmentOfferMatchRead>(accessToken, `/investisseur/offres/${offerId}/startups`, {
    method: "POST",
  })
}

export function getStartupMatching(accessToken: string, offerId: string): Promise<InvestmentOfferMatchRead | null> {
  return request<InvestmentOfferMatchRead | null>(accessToken, `/investisseur/offres/${offerId}/startups`)
}

export function toggleStartupInteret(
  accessToken: string,
  offerId: string,
  projectId: string,
  interesse: boolean,
): Promise<InvestmentOfferMatchRead> {
  return request<InvestmentOfferMatchRead>(
    accessToken,
    `/investisseur/offres/${offerId}/startups/${projectId}/interet`,
    { method: "PATCH", body: JSON.stringify({ interesse }) },
  )
}

export function listStartupsInteressantes(accessToken: string): Promise<StartupInteressante[]> {
  return request<StartupInteressante[]>(accessToken, "/investisseur/offres/interessantes")
}
