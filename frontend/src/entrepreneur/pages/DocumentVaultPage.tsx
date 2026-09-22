import { useEffect, useState } from "react"
import { Link, useOutletContext } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  downloadDocument,
  downloadDocumentVersion,
  getDocumentVersions,
  getProjectDocuments,
  type DocumentType,
  type DocumentVaultItemRead,
  type DocumentVersionRead,
} from "../api/documentVaultApi"
import DocumentPreviewModal from "../components/DocumentPreviewModal"
import { triggerBlobDownload } from "../utils/blobDownload"
import type { MyProjectOutletContext } from "./MyProjectLayout"

// Reflète document_schemas.DocumentType côté backend (CHECK constraint sur
// `documents.document_type`) — seules ces 2 valeurs existent en base pour
// l'instant (I0). Les futurs services (1.1.4 "statuts", 1.1.9 "kbis"...)
// ajouteront chacun leur propre valeur à ce moment-là, pas ici (voir
// docs/plan-implementation-groupe4.md, section 1.1.17).
const DOCUMENT_TYPE_LABEL: Record<DocumentType, string> = {
  entrepreneur_idea: "Présentation du projet",
  other: "Autre",
}

// Raccourci vers le service 1.1.13 (rédaction interactive du pacte de
// fondateurs) — le coffre-fort est l'endroit où l'entrepreneur regarde ses
// documents et remarque qu'il en manque un ; la sidebar ("Mon projet" >
// "Pacte de fondateurs") reste l'entrée principale pour y revenir, ce
// bouton n'est qu'un raccourci contextuel en plus, pas un remplacement.
const PACTE_FONDATEURS_ROUTE = "/entrepreneur/mon-projet/pacte-fondateurs-v2"

function PacteFondateursCTA() {
  return (
    <Link
      to={PACTE_FONDATEURS_ROUTE}
      className="shrink-0 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
    >
      Rédiger le pacte de fondateurs
    </Link>
  )
}

function formatFileSize(bytes: number | null): string {
  if (bytes === null) return "—"
  if (bytes < 1024) return `${bytes} o`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })
}

// Icônes en ligne, même convention que StepDetailPopup.tsx (viewBox 0 0 24 24,
// strokeWidth={2}, `className` reçu du parent) — pas de librairie d'icônes
// installée dans le projet, inutile d'en ajouter une pour 3 pictogrammes.
function FileIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 3v5h5" />
    </svg>
  )
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v12" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m7 10 5 5 5-5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 19h14" />
    </svg>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
    </svg>
  )
}

/**
 * Service 1.1.17 — Coffre-fort documentaire (Groupe 4). Vue de consultation
 * pure côté lecture (`GET /projects/{id}/documents`) ; le téléchargement
 * passe par une route backend authentifiée distincte plutôt qu'une URL
 * Cloudinary exposée telle quelle — voir document_vault_service.py pour
 * pourquoi (le flag Cloudinary `fl_attachment` testé initialement échoue en
 * 400 sur ce compte).
 *
 * Groupée par `document_type` plutôt qu'une liste plate — un entrepreneur
 * avec plusieurs types de documents doit pouvoir distinguer d'un coup d'œil
 * leur origine, même si un seul type existe réellement en base pour
 * l'instant (voir docs/plan-implementation-groupe4.md).
 *
 * Historique des versions : accordéon simple (un seul document ouvert à la
 * fois), chargé à la demande au premier clic sur le contrôle "N versions"
 * plutôt que préchargé pour tous les documents — évite un appel réseau par
 * document dès l'arrivée sur la page alors que la plupart ne seront jamais
 * ouverts. Ce contrôle est masqué quand `version_count <= 1` (rien à
 * comparer) — voir `DocumentVaultItemRead.version_count` côté backend.
 * Contrepartie assumée : rouvrir un document déjà consulté refait l'appel
 * plutôt que de garder un cache — vue peu fréquentée, pas la peine d'ajouter
 * cette complexité pour l'instant.
 *
 * Clic sur le nom d'un document : ouvre son aperçu dans une popup
 * (DocumentPreviewModal.tsx) plutôt que de le télécharger directement — le
 * bouton de téléchargement reste une action séparée à côté. Popup plutôt
 * qu'un panneau latéral : l'app a déjà un composant Modal partagé
 * (shared/components/Modal.tsx, réutilisé ici) mais aucun pattern de panneau
 * latéral existant — cohérent avec l'architecture actuelle plutôt que
 * d'introduire un second paradigme d'UI pour ce seul cas.
 *
 * `project` vient de MyProjectLayout (route parente, voir ce fichier) — pas
 * de second GET /projects/me ici.
 */
export default function DocumentVaultPage() {
  const { accessToken } = useAuth()
  const { project } = useOutletContext<MyProjectOutletContext>()
  const [documents, setDocuments] = useState<DocumentVaultItemRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  // Id du document en cours de téléchargement (version courante) — désactive
  // juste son bouton le temps du fetch.
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  // Accordéon historique : un seul document ouvert à la fois.
  const [expandedDocId, setExpandedDocId] = useState<string | null>(null)
  const [versions, setVersions] = useState<DocumentVersionRead[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [versionsError, setVersionsError] = useState<string | null>(null)
  const [downloadingVersionId, setDownloadingVersionId] = useState<string | null>(null)

  // Document dont l'aperçu est ouvert en popup — null quand la popup est fermée.
  const [previewDoc, setPreviewDoc] = useState<DocumentVaultItemRead | null>(null)

  useEffect(() => {
    if (!accessToken) return
    setIsLoading(true)
    getProjectDocuments(accessToken, project.id)
      .then(setDocuments)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger tes documents."))
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [accessToken, project.id])

  async function handleDownload(doc: DocumentVaultItemRead) {
    if (!accessToken || !doc.original_filename) return
    setError(null)
    setDownloadingId(doc.id)
    try {
      const { blob, filename } = await downloadDocument(accessToken, project.id, doc.id)
      triggerBlobDownload(blob, doc.original_filename ?? filename)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de télécharger ce document.")
    } finally {
      setDownloadingId(null)
    }
  }

  async function handleToggleHistory(documentId: string) {
    if (expandedDocId === documentId) {
      setExpandedDocId(null)
      return
    }

    setExpandedDocId(documentId)
    setVersions([])
    setVersionsError(null)

    if (!accessToken) return
    setVersionsLoading(true)
    try {
      setVersions(await getDocumentVersions(accessToken, project.id, documentId))
    } catch (err) {
      setVersionsError(err instanceof ApiError ? err.message : "Impossible de charger l'historique.")
    } finally {
      setVersionsLoading(false)
    }
  }

  async function handleDownloadVersion(documentId: string, version: DocumentVersionRead) {
    if (!accessToken) return
    setVersionsError(null)
    setDownloadingVersionId(version.id)
    try {
      const { blob, filename } = await downloadDocumentVersion(accessToken, project.id, documentId, version.id)
      triggerBlobDownload(blob, version.original_filename ?? filename)
    } catch (err) {
      setVersionsError(err instanceof ApiError ? err.message : "Impossible de télécharger cette version.")
    } finally {
      setDownloadingVersionId(null)
    }
  }

  if (isLoading) return <LoadingSpinner />

  if (documents.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-semibold text-gray-900">Coffre-fort documentaire</h1>
          <PacteFondateursCTA />
        </div>
        <p className="text-sm text-gray-500">Aucun document pour l'instant.</p>
      </div>
    )
  }

  const groupes = Array.from(new Set(documents.map((doc) => doc.document_type)))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Coffre-fort documentaire</h1>
        <PacteFondateursCTA />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {groupes.map((documentType) => (
        <div key={documentType} className="flex flex-col gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            {DOCUMENT_TYPE_LABEL[documentType] ?? documentType}
          </h2>
          <div className="flex flex-col gap-2">
            {documents
              .filter((doc) => doc.document_type === documentType)
              .map((doc) => {
                const isExpanded = expandedDocId === doc.id
                const hasHistory = doc.version_count > 1

                return (
                  <div key={doc.id} className="rounded-lg border border-gray-200 bg-white">
                    <div className="flex flex-wrap items-center gap-3 p-3">
                      <button
                        type="button"
                        onClick={() => doc.original_filename && setPreviewDoc(doc)}
                        disabled={!doc.original_filename}
                        title={doc.original_filename ? "Aperçu" : undefined}
                        className={`group flex min-w-[140px] flex-1 items-center gap-3 text-left ${
                          doc.original_filename ? "" : "cursor-not-allowed opacity-50"
                        }`}
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                          <FileIcon className="h-[18px] w-[18px]" />
                        </span>

                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-gray-900 group-hover:text-indigo-600">
                            {doc.original_filename ?? "Sans nom"}
                          </span>
                          <span className="flex items-center gap-1.5 text-xs text-gray-400">
                            <span>{formatFileSize(doc.size_bytes)}</span>
                            <span>·</span>
                            <span>{formatDate(doc.created_at)}</span>
                            {downloadingId === doc.id && <span className="text-gray-500">Téléchargement…</span>}
                          </span>
                        </span>
                      </button>

                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleDownload(doc)}
                          disabled={!doc.original_filename || downloadingId === doc.id}
                          title="Télécharger"
                          className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-500 transition hover:border-indigo-300 hover:text-indigo-600 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <DownloadIcon className="h-4 w-4" />
                        </button>

                        {hasHistory && (
                          <button
                            type="button"
                            onClick={() => handleToggleHistory(doc.id)}
                            aria-expanded={isExpanded}
                            className={`flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition ${
                              isExpanded
                                ? "border-indigo-300 bg-indigo-50 text-indigo-600"
                                : "border-gray-200 text-gray-500 hover:border-gray-300 hover:text-gray-700"
                            }`}
                          >
                            <ChevronIcon className={`h-3.5 w-3.5 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                            <span>{doc.version_count} versions</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {hasHistory && isExpanded && (
                      <div className="border-t border-gray-100 py-3 pl-[52px] pr-3">
                        {versionsLoading && <p className="text-xs text-gray-400">Chargement…</p>}
                        {versionsError && <p className="text-xs text-red-600">{versionsError}</p>}

                        {!versionsLoading && !versionsError && (
                          <div className="flex flex-col">
                            {versions.map((version, index) => (
                              <div key={version.id} className="flex gap-3">
                                <div className="flex w-[11px] shrink-0 flex-col items-center">
                                  <span
                                    className={`h-[11px] w-[11px] shrink-0 rounded-full ${
                                      version.is_current ? "bg-amber-400" : "bg-gray-300"
                                    }`}
                                  />
                                  {index !== versions.length - 1 && <span className="mt-1 w-px flex-1 bg-gray-200" />}
                                </div>

                                <div className="flex min-w-0 flex-1 items-center justify-between gap-3 pb-4">
                                  <div className="min-w-0">
                                    <div className="flex items-center gap-2">
                                      <span className="text-sm font-medium text-gray-900">
                                        Version {version.version_number}
                                      </span>
                                      {version.is_current && (
                                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                                          Actuelle
                                        </span>
                                      )}
                                    </div>
                                    <p className="text-xs text-gray-400">
                                      {formatFileSize(version.size_bytes)} · {formatDate(version.created_at)}
                                      {downloadingVersionId === version.id && (
                                        <span className="text-gray-500"> · Téléchargement…</span>
                                      )}
                                    </p>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => handleDownloadVersion(doc.id, version)}
                                    disabled={downloadingVersionId === version.id}
                                    title="Télécharger cette version"
                                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-gray-200 text-gray-500 transition hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-50"
                                  >
                                    <DownloadIcon className="h-3.5 w-3.5" />
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
        </div>
      ))}

      {previewDoc && accessToken && (
        <DocumentPreviewModal
          projectId={project.id}
          documentId={previewDoc.id}
          filename={previewDoc.original_filename ?? "document"}
          accessToken={accessToken}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </div>
  )
}
