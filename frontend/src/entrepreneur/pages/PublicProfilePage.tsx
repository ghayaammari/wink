import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  updateProject,
  uploadProjectLogo,
  upsertPublicProfile,
} from "../api/projectApi"
import { ExtractedFieldFrame } from "../components/ExtractedFieldFrame"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"
import { useDraftSync } from "../hooks/useDraftSync"
import { useExtractedFieldTracking } from "../hooks/useExtractedFieldTracking"
import { extractedText, initialFieldValue } from "../utils/extractedFieldValue"
import { clearDraft, readDraft } from "../utils/formDraft"

// Uniquement website_url : le logo est un fichier image, jamais extrait d'un
// document texte — pas de champ `project_field_value` possible pour lui.
const FIELD_WEBSITE_URL = "project_public_profiles.website_url"

interface Draft {
  websiteUrl: string
}

/** Écran 9 — vitrine publique, optionnel dans le questionnaire : logo (upload
 * Cloudinary) + site web. L'utilisateur peut passer cet écran sans rien
 * remplir (bouton "Passer"). */
export default function PublicProfilePage() {
  const { project, setProject, fieldValues, goNext, goPrevious } =
    useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [FIELD_WEBSITE_URL])
  const draft = project ? readDraft<Draft>(project.id, "public_profile") : null

  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [websiteUrl, setWebsiteUrl] = useState(
    () =>
      draft?.websiteUrl ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_WEBSITE_URL,
        extractedText,
        "",
      ),
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useDraftSync(project?.id, "public_profile", { websiteUrl }, !isSubmitting)

  // Aperçu local de l'image choisie — révoqué à chaque changement pour ne pas
  // accumuler des object URLs en mémoire tant que le composant reste monté.
  useEffect(() => {
    if (!logoFile) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(logoFile)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [logoFile])

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setLogoFile(event.target.files?.[0] ?? null)
  }

  function handleRemoveFile() {
    setLogoFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      let logoUrl: string | undefined
      if (logoFile) {
        const result = await uploadProjectLogo(
          accessToken,
          project.id,
          logoFile,
        )
        logoUrl = result.logo_url
      }

      await upsertPublicProfile(accessToken, project.id, {
        logo_url: logoUrl,
        website_url: websiteUrl || undefined,
        resolved_field_values: tracking.buildResolutions(),
      })
      // upsertPublicProfile met à jour project_public_profiles, pas `projects` —
      // on relit le projet pour récupérer le completion_percentage à jour
      // (le logo/site web comptent dans le calcul, voir _compute_completion).
      const updated = await updateProject(accessToken, project.id, {})
      setProject(updated)
      clearDraft(project.id, "public_profile")
      goNext()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Une erreur est survenue.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">
          Logo
        </label>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="hidden"
          id="logo-upload"
        />

        {previewUrl ? (
          <div className="flex items-center gap-3 rounded-lg border border-gray-300 p-3">
            <img
              src={previewUrl}
              alt="Aperçu du logo"
              className="h-14 w-14 rounded-lg object-cover"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-gray-700">{logoFile?.name}</p>
              <button
                type="button"
                onClick={handleRemoveFile}
                className="text-xs text-red-600 hover:underline"
              >
                Retirer
              </button>
            </div>
          </div>
        ) : (
          <label
            htmlFor="logo-upload"
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-center transition hover:border-indigo-400 hover:bg-indigo-50/50"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="h-8 w-8 text-gray-400"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8.25 12 3.75m0 0L7.5 8.25M12 3.75v13.5"
              />
            </svg>
            <span className="text-sm font-medium text-gray-700">
              Cliquer pour importer une image
            </span>
            <span className="text-xs text-gray-400">
              PNG, JPG — logo de ton projet
            </span>
          </label>
        )}
      </div>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_WEBSITE_URL)}
        touched={tracking.isTouched(FIELD_WEBSITE_URL)}
        onIgnore={() => tracking.ignore(FIELD_WEBSITE_URL)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Site web
          </label>
          <input
            type="url"
            value={websiteUrl}
            onChange={(e) => {
              setWebsiteUrl(e.target.value)
              tracking.markTouched(FIELD_WEBSITE_URL)
            }}
            placeholder="https://..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-between">
        <button
          type="button"
          onClick={goPrevious}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          Précédent
        </button>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={goNext}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            Passer
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Enregistrement..." : "Continuer"}
          </button>
        </div>
      </div>
    </form>
  )
}
