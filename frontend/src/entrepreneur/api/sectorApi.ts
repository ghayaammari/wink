/**
 * Client HTTP pour `backend/entrepreneur/routes/sector_router.py` — service
 * 3.3.5 (conformité sectorielle, HealthTech + FinTech). Même convention que
 * aiActApi.ts : accessToken en premier paramètre, `request<T>` propre à ce
 * fichier (dupliqué plutôt que factorisé, même choix que les autres clients
 * API de ce dossier).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface ComplianceScoreRead {
  score: number | null
  total_obligations: number
  obligations_accomplies: number
}

export type SecteurDetecte = "healthtech" | "fintech" | "aucun"

export interface ProjectSectorDetectionRead {
  id: string
  project_id: string
  // `null` tant que la detection n'a jamais ete lancee.
  secteur_detecte: SecteurDetecte | null
  justification: string | null
  created_at: string
  updated_at: string
}

export type ClasseRisqueHealthtech = "non_dispositif_medical" | "I" | "IIa" | "IIb" | "III"

export interface HealthtechDataProfileRead {
  id: string
  project_id: string
  est_dispositif_medical: boolean | null
  fournit_aide_decision_diagnostique_ou_therapeutique: boolean | null
  risque_deces_ou_deterioration_irreversible: boolean | null
  risque_intervention_chirurgicale_ou_deterioration_grave: boolean | null
  created_at: string
  updated_at: string
}

export type HealthtechDataProfilePatch = Partial<
  Pick<
    HealthtechDataProfileRead,
    | "est_dispositif_medical"
    | "fournit_aide_decision_diagnostique_ou_therapeutique"
    | "risque_deces_ou_deterioration_irreversible"
    | "risque_intervention_chirurgicale_ou_deterioration_grave"
  >
>

export interface ProjectHealthtechClassificationRead {
  id: string
  project_id: string
  classe_risque: ClasseRisqueHealthtech | null
  justification: string | null
  created_at: string
  updated_at: string
}

export type TypeAgrementFintech = "aucun" | "agrement_simplifie" | "agrement_classique"

export interface FintechDataProfileRead {
  id: string
  project_id: string
  gere_fonds_ou_paiements_clients: boolean | null
  volume_mensuel_depasse_3_millions: boolean | null
  propose_transmission_de_fonds: boolean | null
  gere_investissement_ou_actifs: boolean | null
  created_at: string
  updated_at: string
}

export type FintechDataProfilePatch = Partial<
  Pick<
    FintechDataProfileRead,
    | "gere_fonds_ou_paiements_clients"
    | "volume_mensuel_depasse_3_millions"
    | "propose_transmission_de_fonds"
    | "gere_investissement_ou_actifs"
  >
>

export interface ProjectFintechClassificationRead {
  id: string
  project_id: string
  type_agrement: TypeAgrementFintech | null
  justification: string | null
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

export function getSectorDetection(accessToken: string, projectId: string): Promise<ProjectSectorDetectionRead> {
  return request<ProjectSectorDetectionRead>(accessToken, `/projects/${projectId}/sector/detection`)
}

// Appel LLM côté backend (voir sector_detection_diagnostic_service.py) —
// déclenché uniquement par un bouton explicite, même raisonnement que
// runAiActDiagnostic (aiActApi.ts).
export function runSectorDetection(accessToken: string, projectId: string): Promise<ProjectSectorDetectionRead> {
  return request<ProjectSectorDetectionRead>(accessToken, `/projects/${projectId}/sector/detection`, {
    method: "POST",
  })
}

export function getHealthtechProfile(accessToken: string, projectId: string): Promise<HealthtechDataProfileRead> {
  return request<HealthtechDataProfileRead>(accessToken, `/projects/${projectId}/sector/healthtech/profile`)
}

export function updateHealthtechProfile(
  accessToken: string,
  projectId: string,
  patch: HealthtechDataProfilePatch,
): Promise<HealthtechDataProfileRead> {
  return request<HealthtechDataProfileRead>(accessToken, `/projects/${projectId}/sector/healthtech/profile`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  })
}

export function getHealthtechClassification(
  accessToken: string,
  projectId: string,
): Promise<ProjectHealthtechClassificationRead> {
  return request<ProjectHealthtechClassificationRead>(
    accessToken,
    `/projects/${projectId}/sector/healthtech/classification`,
  )
}

export function getFintechProfile(accessToken: string, projectId: string): Promise<FintechDataProfileRead> {
  return request<FintechDataProfileRead>(accessToken, `/projects/${projectId}/sector/fintech/profile`)
}

export function updateFintechProfile(
  accessToken: string,
  projectId: string,
  patch: FintechDataProfilePatch,
): Promise<FintechDataProfileRead> {
  return request<FintechDataProfileRead>(accessToken, `/projects/${projectId}/sector/fintech/profile`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  })
}

export function getFintechClassification(
  accessToken: string,
  projectId: string,
): Promise<ProjectFintechClassificationRead> {
  return request<ProjectFintechClassificationRead>(
    accessToken,
    `/projects/${projectId}/sector/fintech/classification`,
  )
}


// ---------------------------------------------------------------------------
// Diagnostic d'écart HealthTech (service 3.3.6) — mini-roadmap à 3 chapitres,
// voir backend/entrepreneur/schemas/project_healthtech_gap_analysis_schemas.py.
// Contrairement à la classification (auto-recalcul), chaque chapitre est
// généré uniquement par un clic explicite (POST) — un vrai appel LLM+RAG,
// coûteux, à la différence du calcul déterministe gratuit de la classification.
// ---------------------------------------------------------------------------

export type ChapitreHealthtech = "obligations_fabricant" | "evaluation_clinique" | "surveillance_post_commercialisation"

export type StatutChapitreGapAnalysis = "verrouille" | "debloque" | "fait"

export interface ObligationGapAnalysis {
  nom: string
  description: string
  source_id: string | null
  // Suivi manuel côté entrepreneur (coché/décoché), aucun lien avec le
  // recalcul LLM — remis à `false` par le backend à chaque régénération du
  // chapitre/bloc (voir toggle_obligation, `_obligations_to_dict`).
  accompli: boolean
}

export interface ProjectHealthtechGapAnalysisRead {
  id: string
  project_id: string
  chapitre: ChapitreHealthtech
  obligations: { obligations: ObligationGapAnalysis[] }
  justification: string
  created_at: string
  updated_at: string
}

export interface ChapitreGapAnalysisStatusRead {
  cle: ChapitreHealthtech
  titre: string
  statut: StatutChapitreGapAnalysis
  resultat: ProjectHealthtechGapAnalysisRead | null
}

export function getHealthtechGapAnalysis(
  accessToken: string,
  projectId: string,
): Promise<ChapitreGapAnalysisStatusRead[]> {
  return request<ChapitreGapAnalysisStatusRead[]>(accessToken, `/projects/${projectId}/sector/healthtech/gap-analysis`)
}

// Déclenche un vrai appel LLM+RAG pour ce chapitre — rejeté en 409 par le
// backend si le chapitre est encore verrouillé (voir ensure_chapitre_debloque),
// donc le bouton ne doit être affiché que pour un chapitre "debloque" ou
// "fait" côté UI (défense en profondeur, pas la seule protection).
export function generateHealthtechGapAnalysisChapitre(
  accessToken: string,
  projectId: string,
  chapitre: ChapitreHealthtech,
): Promise<ChapitreGapAnalysisStatusRead> {
  return request<ChapitreGapAnalysisStatusRead>(
    accessToken,
    `/projects/${projectId}/sector/healthtech/gap-analysis/${chapitre}`,
    { method: "POST" },
  )
}

// ---------------------------------------------------------------------------
// Service 3.3.6 — diagnostic d'écart, volet FinTech. Bloc unique (pas de
// chapitres, pas de verrouillage) : contrairement à HealthTech, un seul
// GET renvoie le résultat (ou null s'il n'a jamais été généré) et un seul
// POST déclenche/régénère l'unique diagnostic.
// ---------------------------------------------------------------------------

export interface ProjectFintechGapAnalysisRead {
  id: string
  project_id: string
  obligations: { obligations: ObligationGapAnalysis[] }
  justification: string
  created_at: string
  updated_at: string
}

export function getFintechGapAnalysis(
  accessToken: string,
  projectId: string,
): Promise<ProjectFintechGapAnalysisRead | null> {
  return request<ProjectFintechGapAnalysisRead | null>(accessToken, `/projects/${projectId}/sector/fintech/gap-analysis`)
}

export function generateFintechGapAnalysis(
  accessToken: string,
  projectId: string,
): Promise<ProjectFintechGapAnalysisRead> {
  return request<ProjectFintechGapAnalysisRead>(
    accessToken,
    `/projects/${projectId}/sector/fintech/gap-analysis`,
    { method: "POST" },
  )
}

// Bascule le suivi manuel "accompli" d'une obligation — pas d'appel LLM,
// juste une écriture (voir toggle_obligation côté backend). Renvoie le
// statut du chapitre entier (comme generateHealthtechGapAnalysisChapitre)
// pour rester cohérent avec le reste de cette page.
export function toggleHealthtechObligation(
  accessToken: string,
  projectId: string,
  chapitre: ChapitreHealthtech,
  obligationIndex: number,
  accompli: boolean,
): Promise<ChapitreGapAnalysisStatusRead> {
  return request<ChapitreGapAnalysisStatusRead>(
    accessToken,
    `/projects/${projectId}/sector/healthtech/gap-analysis/${chapitre}/obligations/${obligationIndex}`,
    { method: "PATCH", body: JSON.stringify({ accompli }) },
  )
}

// Même rôle côté FinTech (bloc unique, pas de chapitre à préciser).
export function toggleFintechObligation(
  accessToken: string,
  projectId: string,
  obligationIndex: number,
  accompli: boolean,
): Promise<ProjectFintechGapAnalysisRead> {
  return request<ProjectFintechGapAnalysisRead>(
    accessToken,
    `/projects/${projectId}/sector/fintech/gap-analysis/obligations/${obligationIndex}`,
    { method: "PATCH", body: JSON.stringify({ accompli }) },
  )
}

// Score HealthTech : agrège tous les chapitres deja generes (un seul score
// pour tout le diagnostic, voir project_healthtech_gap_analysis_service.get_score).
export function getHealthtechGapAnalysisScore(accessToken: string, projectId: string): Promise<ComplianceScoreRead> {
  return request<ComplianceScoreRead>(accessToken, `/projects/${projectId}/sector/healthtech/gap-analysis/score`)
}

// Score FinTech : bloc unique, voir project_fintech_gap_analysis_service.get_score.
export function getFintechGapAnalysisScore(accessToken: string, projectId: string): Promise<ComplianceScoreRead> {
  return request<ComplianceScoreRead>(accessToken, `/projects/${projectId}/sector/fintech/gap-analysis/score`)
}


// Telecharge le rapport PDF HealthTech (agregeant tous les chapitres deja
// generes, voir get_report_pdf cote backend) -- meme mecanisme que
// downloadRgpdReport (rgpdApi.ts), reponse binaire, pas JSON.
export async function downloadHealthtechGapAnalysisReport(accessToken: string, projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/sector/healthtech/gap-analysis/report`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "rapport-conformite-healthtech.pdf"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

// Meme rôle côté FinTech (bloc unique).
export async function downloadFintechGapAnalysisReport(accessToken: string, projectId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/sector/fintech/gap-analysis/report`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "rapport-conformite-fintech.pdf"
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
