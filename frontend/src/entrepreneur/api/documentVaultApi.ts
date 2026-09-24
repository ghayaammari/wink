/**
 * Client HTTP pour `backend/entrepreneur/routes/document_vault_router.py` —
 * service 1.1.17 (coffre-fort documentaire). Même convention que
 * nameAvailabilityApi.ts : accessToken en premier paramètre.
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// Élargi (25/09/2026, service 1.1.4 statuts) — `documents.document_type` a
// déjà les 4 valeurs en base depuis la migration d2e3f4a5b6c7 (voir Document
// côté backend), mais ce type ici n'avait jamais été mis à jour en même
// temps que "pacte_fondateurs" (service 1.1.13) : un pacte déjà généré
// s'affichait dans le coffre-fort avec son nom technique brut au lieu d'un
// libellé (voir DOCUMENT_TYPE_LABEL dans DocumentVaultPage.tsx, même bug).
export type DocumentType =
  | "entrepreneur_idea"
  | "other"
  | "pacte_fondateurs"
  | "statuts"
  // Service 1.1.5 : attestation de parution déposée par l'entrepreneur.
  | "attestation_annonce_legale"

export interface DocumentVaultItemRead {
  id: string
  document_type: DocumentType
  original_filename: string | null
  mime_type: string | null
  size_bytes: number | null
  created_at: string
  version_count: number
}

export interface DocumentVersionRead {
  id: string
  version_number: number
  original_filename: string
  mime_type: string
  size_bytes: number
  created_at: string
  is_current: boolean
}

async function extractErrorDetail(response: globalThis.Response): Promise<string> {
  let detail = response.statusText
  try {
    const body = await response.json()
    detail = body.detail ?? detail
  } catch {
    // Réponse sans corps JSON exploitable — on garde statusText.
  }
  return detail
}

async function request<T>(accessToken: string, path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response))
  }
  return (await response.json()) as T
}

/**
 * Fetch authentifié d'un fichier (pas du JSON) : téléchargement de la version
 * courante ou d'une version historique d'un document — voir downloadDocument()
 * et downloadDocumentVersion() ci-dessous, qui ne diffèrent que par le path
 * appelé. Retourne un Blob plutôt qu'une URL : un lien `<a href>` classique ne
 * peut pas porter le header `Authorization`, donc DocumentVaultPage.tsx doit
 * déclencher ce fetch lui-même puis créer une URL d'objet temporaire
 * (`URL.createObjectURL`) pour lancer le téléchargement.
 */
async function fetchBlobDownload(accessToken: string, path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response))
  }

  const blob = await response.blob()

  // Nom de fichier extrait du header Content-Disposition posé par le backend
  // (`attachment; filename="X.pdf"`) — filet de sécurité seulement, en
  // pratique DocumentVaultPage.tsx préfère le nom déjà connu côté frontend.
  const disposition = response.headers.get("Content-Disposition") ?? ""
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const filename = match ? match[1] : "document"

  return { blob, filename }
}

export function getProjectDocuments(accessToken: string, projectId: string): Promise<DocumentVaultItemRead[]> {
  return request<DocumentVaultItemRead[]>(accessToken, `/projects/${projectId}/documents`)
}

export function downloadDocument(
  accessToken: string,
  projectId: string,
  documentId: string,
): Promise<{ blob: Blob; filename: string }> {
  return fetchBlobDownload(accessToken, `/projects/${projectId}/documents/${documentId}/download`)
}

export function getDocumentVersions(
  accessToken: string,
  projectId: string,
  documentId: string,
): Promise<DocumentVersionRead[]> {
  return request<DocumentVersionRead[]>(accessToken, `/projects/${projectId}/documents/${documentId}/versions`)
}

export function downloadDocumentVersion(
  accessToken: string,
  projectId: string,
  documentId: string,
  versionId: string,
): Promise<{ blob: Blob; filename: string }> {
  return fetchBlobDownload(
    accessToken,
    `/projects/${projectId}/documents/${documentId}/versions/${versionId}/download`,
  )
}
