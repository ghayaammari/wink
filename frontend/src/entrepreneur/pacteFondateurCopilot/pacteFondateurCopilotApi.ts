/**
 * Client HTTP pour `backend/entrepreneur/routes/pacte_fondateur_copilot_router.py`
 * -- service 1.1.13, categorie 3 (copilot conversationnel du pacte de
 * fondateurs). Meme convention que roadmapApi.ts/documentGenerationApi.ts :
 * accessToken en premier parametre, `request<T>` local.
 *
 * ISOLATION VOLONTAIRE (25/09/2026, meme decision que le backend) : ce
 * fichier vit sous entrepreneur/pacteFondateurCopilot/ plutot que dans
 * entrepreneur/api/ (emplacement standard des autres clients HTTP) -- la
 * binome ayant deja commence un composant de chat/copilot cote frontend,
 * tout ce qui touche ce widget (client HTTP + composants) est regroupe dans
 * un seul dossier pour eviter toute collision au moment de la fusion.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export interface PacteFondateurCopilotSource {
  source_type: string
  source_id: string
  citation: string | null
  chunk_texte: string | null
}

export interface PacteFondateurCopilotReponse {
  reponse: string
  sources: PacteFondateurCopilotSource[]
}

export interface PacteFondateurCopilotHistoryItem {
  question: string
  code_clause_contexte: string | null
  reponse: string
  sources: PacteFondateurCopilotSource[]
  created_at: string
}

async function request<T>(
  accessToken: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
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
      // Reponse sans corps JSON exploitable -- on garde statusText.
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

/** Historique complet de la conversation du projet (vide si aucun message
 * n'a encore ete envoye) -- a appeler au montage de la bulle pour reafficher
 * les echanges precedents (exigence actee : l'historique se persiste). */
export function getHistorique(
  accessToken: string,
  projectId: string,
): Promise<{ echanges: PacteFondateurCopilotHistoryItem[] }> {
  return request(accessToken, `/projects/${projectId}/pacte-fondateur-copilot/messages`)
}

export function poserQuestion(
  accessToken: string,
  projectId: string,
  question: string,
  codeClauseContexte: string | null,
): Promise<PacteFondateurCopilotReponse> {
  return request<PacteFondateurCopilotReponse>(
    accessToken,
    `/projects/${projectId}/pacte-fondateur-copilot/questions`,
    {
      method: "POST",
      body: JSON.stringify({ question, code_clause_contexte: codeClauseContexte }),
    },
  )
}

/** Explication automatique de clause -- service 1.1.15 (27/09/2026, seul
 * mecanisme d'explication restant apres consolidation, voir la docstring de
 * PacteFondateurCopilotWidget.tsx). Appelee par le widget a chaque nouvelle
 * section affichee, PAS par une saisie utilisateur -- `null` est une reponse
 * normale (section sans clause unique a expliquer), pas une erreur. */
export interface PacteFondateurAutoExplication {
  question: string
  reponse: string
}

export function pousserExplicationAutomatique(
  accessToken: string,
  projectId: string,
  documentType: string,
  codeSection: string,
): Promise<PacteFondateurAutoExplication | null> {
  return request<PacteFondateurAutoExplication | null>(
    accessToken,
    `/projects/${projectId}/pacte-fondateur-copilot/auto-explication`,
    {
      method: "POST",
      body: JSON.stringify({ document_type: documentType, code_section: codeSection }),
    },
  )
}
