import { type ChangeEvent, useRef, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { uploadDocument } from "../api/projectApi"
import ProjectSectionCard from "../components/ProjectSectionCard"
import { countPendingByTable } from "../utils/fieldValueTable"
import type { MyProjectOutletContext } from "./MyProjectLayout"

/**
 * Landing "Mon Projet" — 3 cards vers les sections détaillées (Informations
 * générales/légales, Vitrine publique), chacune avec un badge = nombre de
 * `project_field_values` en attente pour sa table. Le bouton d'import est ici
 * (pas dans une sous-section précise) car l'extraction touche potentiellement
 * les 3 tables à la fois — voir spec Notion "Page Mon Projet".
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente) : cette
 * page ne fait plus son propre fetch au montage — voir ce fichier pour le
 * pourquoi (optimisation "chargement lourd").
 */
export default function MyProjectPage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const pendingCounts = countPendingByTable(fieldValues)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) handleUpload(file)
    // Permet de réimporter le même fichier deux fois de suite (sinon `onChange`
    // ne se redéclenche pas si la sélection ne change pas).
    event.target.value = ""
  }

  async function handleUpload(file: File) {
    if (!accessToken) return
    setError(null)
    setIsUploading(true)
    try {
      await uploadDocument(accessToken, project.id, file)
      await refresh()
    } catch (err) {
      // Le document peut avoir été importé même si cette erreur est levée
      // (échec de l'extraction seulement, voir document_service.py) — on
      // rafraîchit quand même au cas où une partie a réussi.
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
      await refresh().catch(() => {})
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Mon projet</h1>

        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          className="hidden"
          id="mon-projet-upload"
        />
        <label
          htmlFor="mon-projet-upload"
          className={`cursor-pointer rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 ${
            isUploading ? "pointer-events-none opacity-50" : ""
          }`}
        >
          {isUploading ? "Analyse en cours..." : "Importer un document"}
        </label>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <ProjectSectionCard
          to="/entrepreneur/mon-projet/informations-generales"
          title="Informations générales"
          description="Description, secteur, équipe, technologies, localisation"
          pendingCount={pendingCounts["projects"] ?? 0}
        />
        <ProjectSectionCard
          to="/entrepreneur/mon-projet/informations-legales"
          title="Informations légales"
          description="Identité légale de la société"
          pendingCount={pendingCounts["project_legal_profiles"] ?? 0}
        />
        <ProjectSectionCard
          to="/entrepreneur/mon-projet/vitrine-publique"
          title="Vitrine publique"
          description="Logo, site web, présentation publique"
          pendingCount={pendingCounts["project_public_profiles"] ?? 0}
        />
      </div>
    </div>
  )
}
