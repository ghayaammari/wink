/**
 * Client HTTP pour `backend/entrepreneur/routes/certification_router.py` —
 * service 3.3.11 (Accompagnement accéléré vers les certifications de
 * sécurité). Même convention que rgpdApi.ts.
 *
 * V1 limitée à SecNumCloud (voir migration q4d6f8a0b2c4 côté backend) : pas
 * de paramètre `typeCertification` dans les fonctions ci-dessous, chemins
 * d'URL en dur sur `/secnumcloud/...` -- à généraliser quand ISO 27001/SOC 2
 * seront ajoutés, pas avant.
 *
 * `runSecnumcloudDiagnostic` (ajoutée le 22/09/2026 avec le 6e sous-agent de
 * compliance_agent) renvoie les étapes du parcours -- l'estimation générée
 * dans le même appel agent se récupère séparément via
 * `getSecnumcloudEstimation` (même principe que le score : deux widgets
 * indépendants côté page).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ObligationStatut = "a_faire" | "fait"

export interface ComplianceScoreRead {
  score: number | null
  total_obligations: number
  obligations_accomplies: number
}

export interface ProjectCertificationObligationRead {
  id: string
  project_id: string
  type_certification: "secnumcloud"
  nom: string
  description: string
  ordre: number
  statut: ObligationStatut
  legal_text_id: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCertificationEstimationRead {
  id: string
  project_id: string
  type_certification: "secnumcloud"
  delai_mois_min: number
  delai_mois_max: number
  cout_estime_min: number
  cout_estime_max: number
  justification: string
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

export function getSecnumcloudObligations(
  accessToken: string,
  projectId: string,
): Promise<ProjectCertificationObligationRead[]> {
  return request<ProjectCertificationObligationRead[]>(
    accessToken,
    `/projects/${projectId}/certification/secnumcloud/obligations`,
  )
}

export function updateSecnumcloudObligationStatut(
  accessToken: string,
  projectId: string,
  obligationId: string,
  statut: ObligationStatut,
): Promise<ProjectCertificationObligationRead> {
  return request<ProjectCertificationObligationRead>(
    accessToken,
    `/projects/${projectId}/certification/secnumcloud/obligations/${obligationId}`,
    { method: "PATCH", body: JSON.stringify({ statut }) },
  )
}

export function getSecnumcloudScore(accessToken: string, projectId: string): Promise<ComplianceScoreRead> {
  return request<ComplianceScoreRead>(accessToken, `/projects/${projectId}/certification/secnumcloud/score`)
}

export function runSecnumcloudDiagnostic(
  accessToken: string,
  projectId: string,
): Promise<ProjectCertificationObligationRead[]> {
  return request<ProjectCertificationObligationRead[]>(
    accessToken,
    `/projects/${projectId}/certification/secnumcloud/diagnostic`,
    { method: "POST" },
  )
}

export function getSecnumcloudEstimation(
  accessToken: string,
  projectId: string,
): Promise<ProjectCertificationEstimationRead | null> {
  return request<ProjectCertificationEstimationRead | null>(
    accessToken,
    `/projects/${projectId}/certification/secnumcloud/estimation`,
  )
}
