/**
 * Client HTTP pour backend/investisseur (profil) — même pattern que
 * researcherProfileApi.ts : réutilise ApiError de authApi.ts, pas de state
 * ici (voir AuthContext pour les tokens).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ProfileCompletion = "0%" | "33%" | "67%" | "100%"
export type InvestorType = "vc" | "business_angel" | "family_office" | "corporate_vc" | "fonds_public" | "autre"

export interface InvestorProfileRead {
  id: string
  user_id: string
  organization_name: string | null
  investor_type: InvestorType | null
  investment_thesis: string | null
  contact_email: string | null
  profile_completion: ProfileCompletion
  created_at: string
  updated_at: string
}

export interface InvestorOnboardingRequest {
  investor_type: InvestorType
  organization_name?: string | null
  investment_thesis?: string | null
  contact_email?: string | null
}

export interface InvestorProfileUpdate {
  investor_type?: InvestorType
  organization_name?: string | null
  investment_thesis?: string | null
  contact_email?: string | null
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

export function getMyInvestorProfile(accessToken: string): Promise<InvestorProfileRead> {
  return request<InvestorProfileRead>("/investisseur/profile", accessToken)
}

export function completeOnboarding(
  accessToken: string,
  data: InvestorOnboardingRequest,
): Promise<InvestorProfileRead> {
  return request<InvestorProfileRead>("/investisseur/onboarding", accessToken, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export function updateInvestorProfile(
  accessToken: string,
  data: InvestorProfileUpdate,
): Promise<InvestorProfileRead> {
  return request<InvestorProfileRead>("/investisseur/profile", accessToken, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}