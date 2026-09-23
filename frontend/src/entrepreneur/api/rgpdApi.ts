/**
 * Client HTTP pour `backend/entrepreneur/routes/rgpd_router.py` — service
 * 3.3.1 (diagnostic RGPD). Même convention que `roadmapApi.ts` : accessToken
 * en premier paramètre, `request<T>` propre à ce fichier (pas de client HTTP
 * générique partagé pour l'instant, voir la même remarque dans roadmapApi.ts).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ObligationStatut = "a_faire" | "fait"

// Tri-état : `null` = pas encore répondu, distinct de `false` (voir docstring
// du modèle backend compliance_data_profile.py). Les 3 valeurs sont
// affichées et settables individuellement côté UI (RgpdDiagnosticPage).
export interface ComplianceDataProfileRead {
  id: string
  project_id: string
  collecte_donnees_sensibles: boolean | null
  collecte_donnees_mineurs: boolean | null
  profilage: boolean | null
  partage_avec_tiers: boolean | null
  transfert_hors_ue: boolean | null
  created_at: string
  updated_at: string
}

// Un seul champ à la fois envoyé en pratique (voir RgpdDiagnosticPage), mais
// le type reste un Partial complet pour matcher ComplianceDataProfileUpdate
// côté backend (exclude_unset=True : les champs absents ne sont pas touchés).
export type ComplianceDataProfilePatch = Partial<
  Pick<
    ComplianceDataProfileRead,
    | "collecte_donnees_sensibles"
    | "collecte_donnees_mineurs"
    | "profilage"
    | "partage_avec_tiers"
    | "transfert_hors_ue"
  >
>

export interface ComplianceScoreRead {
  score: number | null
  total_obligations: number
  obligations_accomplies: number
}

export interface ProjectRgpdObligationRead {
  id: string
  project_id: string
  nom: string
  description: string
  statut: ObligationStatut
  legal_text_id: string | null
  // Regroupement demande le 17/09/2026 : permet d'afficher les obligations
  // liees a une AIPD a part du reste (voir RgpdDiagnosticPage.tsx).
  lie_a_aipd: boolean
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

export function getRgpdProfile(accessToken: string, projectId: string): Promise<ComplianceDataProfileRead> {
  return request<ComplianceDataProfileRead>(accessToken, `/projects/${projectId}/rgpd/profile`)
}

export function updateRgpdProfile(
  accessToken: string,
  projectId: string,
  patch: ComplianceDataProfilePatch,
): Promise<ComplianceDataProfileRead> {
  return request<ComplianceDataProfileRead>(accessToken, `/projects/${projectId}/rgpd/profile`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  })
}

export function getRgpdObligations(accessToken: string, projectId: string): Promise<ProjectRgpdObligationRead[]> {
  return request<ProjectRgpdObligationRead[]>(accessToken, `/projects/${projectId}/rgpd/obligations`)
}

export function updateRgpdObligationStatut(
  accessToken: string,
  projectId: string,
  obligationId: string,
  statut: ObligationStatut,
): Promise<ProjectRgpdObligationRead> {
  return request<ProjectRgpdObligationRead>(
    accessToken,
    `/projects/${projectId}/rgpd/obligations/${obligationId}`,
    { method: "PATCH", body: JSON.stringify({ statut }) },
  )
}

// Régénération majeure (voir docstring backend rgpd_diagnostic_service.py) —
// déclenchée uniquement par le bouton explicite "Recalculer mes obligations"
// dans RgpdDiagnosticPage, jamais automatiquement après un updateRgpdProfile.
export function runRgpdDiagnostic(accessToken: string, projectId: string): Promise<ProjectRgpdObligationRead[]> {
  return request<ProjectRgpdObligationRead[]>(accessToken, `/projects/${projectId}/rgpd/diagnostic`, {
    method: "POST",
  })
}

// Score de conformité (% d'obligations "fait") — recalculé côté backend à
// la volée à chaque appel, voir compliance_score_service.py.
export function getRgpdScore(accessToken: string, projectId: string): Promise<ComplianceScoreRead> {
  return request<ComplianceScoreRead>(accessToken, `/projects/${projectId}/rgpd/score`)
}


// Telecharge le rapport PDF (voir compliance_report_service.py cote
// backend) -- reponse binaire, pas JSON : fonction dediee plutot que
// `request<T>` (qui fait toujours response.json()). Declenche directement
// le telechargement navigateur (createObjectURL + <a> temporaire).
export async function downloadRgpdReport(accessToken: string, projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/rgpd/report`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "rapport-conformite-rgpd.pdf"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
