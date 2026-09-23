/**
 * Client HTTP pour `backend/entrepreneur/routes/ai_act_router.py` — service
 * 3.3.12 (diagnostic AI Act). Même convention que rgpdApi.ts : accessToken
 * en premier paramètre, `request<T>` propre à ce fichier.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type ObligationStatut = "a_faire" | "fait"

export type CategorieRisqueAiAct = "interdit" | "haut_risque" | "risque_limite" | "gouvernance_gpai" | "minimal"

// Tri-état : `null` = pas encore répondu (voir docstring ai_act_data_profile_schemas.py).
// `utilise_ia` est un champ "porte" : s'il vaut `false`, les 5 champs
// conditionnels ci-dessous sont sans objet (voir ai_act_diagnostic_service.run_diagnostic
// côté backend, qui court-circuite tout appel LLM dans ce cas).
export interface AiActDataProfileRead {
  id: string
  project_id: string
  utilise_ia: boolean | null
  usage_biometrie_ou_identification: boolean | null
  usage_scoring_emploi_credit_ou_education: boolean | null
  usage_infrastructure_ou_securite_critique: boolean | null
  interagit_ou_genere_contenu_pour_utilisateurs: boolean | null
  developpe_modele_ia_usage_general: boolean | null
  created_at: string
  updated_at: string
}

export type AiActDataProfilePatch = Partial<
  Pick<
    AiActDataProfileRead,
    | "utilise_ia"
    | "usage_biometrie_ou_identification"
    | "usage_scoring_emploi_credit_ou_education"
    | "usage_infrastructure_ou_securite_critique"
    | "interagit_ou_genere_contenu_pour_utilisateurs"
    | "developpe_modele_ia_usage_general"
  >
>

export interface ProjectAiActClassificationRead {
  id: string
  project_id: string
  // `null` tant que le diagnostic n'a jamais été lancé.
  categorie_risque: CategorieRisqueAiAct | null
  justification: string | null
  created_at: string
  updated_at: string
}

export interface ComplianceScoreRead {
  score: number | null
  total_obligations: number
  obligations_accomplies: number
}

export interface ProjectAiActObligationRead {
  id: string
  project_id: string
  nom: string
  description: string
  statut: ObligationStatut
  legal_text_id: string | null
  created_at: string
  updated_at: string
}

// Réponse combinée du POST diagnostic (voir AiActDiagnosticRunResult côté backend) :
// classification ET obligations en un seul retour, pour éviter un second aller-retour.
export interface AiActDiagnosticRunResult {
  classification: ProjectAiActClassificationRead
  obligations: ProjectAiActObligationRead[]
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

export function getAiActProfile(accessToken: string, projectId: string): Promise<AiActDataProfileRead> {
  return request<AiActDataProfileRead>(accessToken, `/projects/${projectId}/ai-act/profile`)
}

export function updateAiActProfile(
  accessToken: string,
  projectId: string,
  patch: AiActDataProfilePatch,
): Promise<AiActDataProfileRead> {
  return request<AiActDataProfileRead>(accessToken, `/projects/${projectId}/ai-act/profile`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  })
}

export function getAiActClassification(
  accessToken: string,
  projectId: string,
): Promise<ProjectAiActClassificationRead> {
  return request<ProjectAiActClassificationRead>(accessToken, `/projects/${projectId}/ai-act/classification`)
}

export function getAiActObligations(
  accessToken: string,
  projectId: string,
): Promise<ProjectAiActObligationRead[]> {
  return request<ProjectAiActObligationRead[]>(accessToken, `/projects/${projectId}/ai-act/obligations`)
}

export function updateAiActObligationStatut(
  accessToken: string,
  projectId: string,
  obligationId: string,
  statut: ObligationStatut,
): Promise<ProjectAiActObligationRead> {
  return request<ProjectAiActObligationRead>(
    accessToken,
    `/projects/${projectId}/ai-act/obligations/${obligationId}`,
    { method: "PATCH", body: JSON.stringify({ statut }) },
  )
}

// Régénération majeure (voir docstring backend ai_act_diagnostic_service.py) —
// déclenchée uniquement par le bouton explicite "Recalculer mon diagnostic"
// dans AiActDiagnosticPage, jamais automatiquement après un updateAiActProfile.
export function runAiActDiagnostic(accessToken: string, projectId: string): Promise<AiActDiagnosticRunResult> {
  return request<AiActDiagnosticRunResult>(accessToken, `/projects/${projectId}/ai-act/diagnostic`, {
    method: "POST",
  })
}

// Même rôle que getRgpdScore (rgpdApi.ts), non répété en détail ici.
export function getAiActScore(accessToken: string, projectId: string): Promise<ComplianceScoreRead> {
  return request<ComplianceScoreRead>(accessToken, `/projects/${projectId}/ai-act/score`)
}


// Telecharge le rapport PDF (voir compliance_report_service.py cote
// backend) -- reponse binaire, pas JSON : fonction dediee plutot que
// `request<T>` (qui fait toujours response.json()). Declenche directement
// le telechargement navigateur (createObjectURL + <a> temporaire).
export async function downloadAiActReport(accessToken: string, projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/ai-act/report`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "rapport-conformite-ai-act.pdf"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
