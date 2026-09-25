/**
 * Client HTTP pour `backend/entrepreneur/routes/copilot_router.py` — copilot
 * conversationnel de conformite, desormais organise en conversations
 * persistees (voir ProjectCopilotConversation) plutot qu'un historique
 * ephemere renvoye a chaque appel (V1 revue le 20/09/2026 — demande d'une
 * barre laterale avec plusieurs conversations, comme Claude).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type CopilotRole = "user" | "assistant"

export type DomaineRedirection = "rgpd" | "ai-act" | "secteur"

// Domaine du rapport telechargeable propose apres un "Terminer" (voir
// CopilotContext.tsx/CopilotPage.tsx) -- distinct de DomaineRedirection
// ("secteur" y est un seul domaine de redirection, mais deux rapports PDF
// differents existent derriere selon le secteur detecte : healthtech ou
// fintech, voir project_healthtech_gap_analysis_service.py/
// project_fintech_gap_analysis_service.py).
export type RapportDomaine = "rgpd" | "ai-act" | "healthtech" | "fintech"

// Champs alignes exactement sur backend/entrepreneur/schemas/copilot_schemas.py
// (meme convention snake_case que rediriger_vers deja utilise avant cette
// revision -- pas de camelCase cote client pour les champs qui traversent
// l'API, voir CopilotContext.tsx pour la conversion en type d'affichage).
export interface CopilotMessage {
  role: CopilotRole
  content: string
  rediriger_vers?: DomaineRedirection | null
  rapport_disponible?: RapportDomaine | null
  ancrage_verifie?: boolean | null
}

export interface CopilotMessageResponse {
  reponse: string
  rediriger_vers: DomaineRedirection | null
  // null = pas de verification effectuee (reponse generale sans recherche
  // dans le corpus) OU verification indisponible -- distinct de false
  // (verification faite, affirmations non etayees trouvees). Voir
  // agents/shared/groq_runtime/grounding_verification_service.py.
  ancrage_verifie: boolean | null
}

export interface CopilotConversationSummary {
  id: string
  titre: string
  created_at: string
  updated_at: string
}

export interface CopilotConversationDetail extends CopilotConversationSummary {
  messages: CopilotMessage[]
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
      // Reponse sans corps JSON exploitable — on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }
  // 201/204 (creation, pas de corps) — retour explicite pour ne pas tenter
  // de parser un corps vide en JSON.
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function createConversation(accessToken: string, projectId: string): Promise<CopilotConversationSummary> {
  return request<CopilotConversationSummary>(accessToken, `/projects/${projectId}/copilot/conversations`, {
    method: "POST",
  })
}

export function listConversations(accessToken: string, projectId: string): Promise<CopilotConversationSummary[]> {
  return request<CopilotConversationSummary[]>(accessToken, `/projects/${projectId}/copilot/conversations`)
}

export function getConversation(
  accessToken: string,
  projectId: string,
  conversationId: string,
): Promise<CopilotConversationDetail> {
  return request<CopilotConversationDetail>(
    accessToken,
    `/projects/${projectId}/copilot/conversations/${conversationId}`,
  )
}

export function sendCopilotMessage(
  accessToken: string,
  projectId: string,
  conversationId: string,
  content: string,
  // Voir CopilotMessageRequest.tronquer_a (backend) -- uniquement pour
  // "editer un message precedent et renvoyer" (CopilotPage.tsx).
  tronquerA?: number,
): Promise<CopilotMessageResponse> {
  return request<CopilotMessageResponse>(
    accessToken,
    `/projects/${projectId}/copilot/conversations/${conversationId}/message`,
    {
      method: "POST",
      body: JSON.stringify({ content, tronquer_a: tronquerA ?? null }),
    },
  )
}
