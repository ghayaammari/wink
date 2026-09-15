import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import Drawer from "../../shared/components/Drawer"
import { downloadDocument, downloadDocumentVersion } from "../api/documentVaultApi"
import { triggerBlobDownload } from "../utils/blobDownload"

interface DocumentPreviewModalProps {
  projectId: string
  documentId: string
  // Absent = version courante (clic sur une ligne du coffre-fort). Fourni =
  // une version précise de l'historique — même composant réutilisable pour
  // les deux cas, seul l'endpoint appelé change (voir fetchBlob ci-dessous).
  versionId?: string
  filename: string
  accessToken: string
  onClose: () => void
}

/**
 * Aperçu d'un document du coffre-fort (service 1.1.17), ouvert dans un tiroir
 * qui glisse depuis la droite au clic sur son nom — trois placements comparés
 * dans un artefact (popup centrée / panneau split / tiroir) avant ce choix,
 * voir docs/documentation-implementation.md. Réutilise le tiroir générique
 * partagé (shared/components/Drawer.tsx, même fermeture Échap/clic dehors que
 * Modal.tsx) plutôt qu'un composant dédié.
 *
 * Nom de fichier resté "...Modal.tsx" malgré le passage en tiroir : le pont
 * vers l'ordinateur de l'utilisateur ne permet pas de renommer/supprimer un
 * fichier proprement depuis cette session (voir contrainte notée dans
 * docs/documentation-implementation.md) — dette mineure assumée, à renommer
 * en DocumentPreviewDrawer.tsx manuellement si souhaité.
 *
 * Réutilise les mêmes endpoints authentifiés que le téléchargement
 * (downloadDocument/downloadDocumentVersion) — le Blob récupéré porte déjà
 * son type MIME (`blob.type`, posé par le backend via `media_type`, voir
 * document_vault_router.py), pas besoin de le faire suivre en prop séparée.
 *
 * Rendu par type : `<iframe>` pour un PDF (visualiseur natif du navigateur,
 * aucune dépendance PDF.js à ajouter), `<img>` pour une image, et un repli
 * "aperçu non disponible" + bouton télécharger pour tout le reste — un
 * document du coffre-fort n'est pas garanti être un PDF à long terme (1.1.9,
 * 1.1.4... pourront y déposer d'autres types).
 */
export default function DocumentPreviewModal({
  projectId,
  documentId,
  versionId,
  filename,
  accessToken,
  onClose,
}: DocumentPreviewModalProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    setIsLoading(true)
    setError(null)
    setPreviewUrl(null)
    setBlob(null)

    const fetchBlob = versionId
      ? downloadDocumentVersion(accessToken, projectId, documentId, versionId)
      : downloadDocument(accessToken, projectId, documentId)

    fetchBlob
      .then(({ blob: fetchedBlob }) => {
        objectUrl = URL.createObjectURL(fetchedBlob)
        setPreviewUrl(objectUrl)
        setBlob(fetchedBlob)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger l'aperçu."))
      .finally(() => setIsLoading(false))

    // Révoque l'URL d'objet au démontage (fermeture du tiroir ou changement
    // de document) — sinon le Blob reste en mémoire tant que l'onglet est ouvert.
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [accessToken, projectId, documentId, versionId])

  function handleDownload() {
    if (blob) triggerBlobDownload(blob, filename)
  }

  const mimeType = blob?.type ?? ""
  const isPdf = mimeType === "application/pdf"
  const isImage = mimeType.startsWith("image/")

  return (
    <Drawer title={filename} onClose={onClose}>
      <div className="flex h-full flex-col gap-3">
        {isLoading && <p className="text-sm text-gray-500">Chargement de l'aperçu…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!isLoading && !error && previewUrl && isPdf && (
          <iframe
            src={previewUrl}
            title={filename}
            className="h-full min-h-[60vh] w-full rounded-lg border border-gray-200"
          />
        )}

        {!isLoading && !error && previewUrl && isImage && (
          <img
            src={previewUrl}
            alt={filename}
            className="max-h-[70vh] w-full rounded-lg border border-gray-200 object-contain"
          />
        )}

        {!isLoading && !error && previewUrl && !isPdf && !isImage && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-200 py-10 text-center">
            <p className="text-sm text-gray-600">Aperçu non disponible pour ce type de fichier.</p>
            <button
              type="button"
              onClick={handleDownload}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
              Télécharger pour consulter
            </button>
          </div>
        )}
      </div>
    </Drawer>
  )
}
