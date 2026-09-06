import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  uploadProjectLogo,
  upsertPublicProfile,
  type ProjectPublicProfileRead,
  type ProjectPublicProfileUpdate,
  type ProjectVisibility,
} from "../api/projectApi"
import { VISIBILITY_OPTIONS } from "../utils/projectVisibilityOptions"

interface UpdatePublicProfileFormProps {
  projectId: string
  /** `null` si l'écran 9 (facultatif) n'a jamais été soumis — le formulaire
   * démarre vide, `upsertPublicProfile` crée la ligne au premier enregistrement. */
  publicProfile: ProjectPublicProfileRead | null
  accessToken: string
  onSaved: () => void
  onCancel: () => void
}

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

/**
 * Formulaire du popup "Mettre à jour" (Vitrine publique, table
 * `project_public_profiles`). `upsertPublicProfile` (POST, déjà un upsert côté
 * backend — voir project_service.upsert_public_profile) sert à la fois à la
 * création (écran 9) et à cette mise à jour : aucune route ni fonction service
 * supplémentaire nécessaire, contrairement à "Informations légales".
 *
 * Logo : un seul fichier choisi ici, prévisualisé localement — l'upload vers
 * Cloudinary (uploadProjectLogo) n'est déclenché qu'au clic sur "Enregistrer",
 * dans le même mouvement que le reste du formulaire (voir handleSubmit),
 * jamais tout seul au moment de la sélection du fichier.
 */
export default function UpdatePublicProfileForm({
  projectId,
  publicProfile,
  accessToken,
  onSaved,
  onCancel,
}: UpdatePublicProfileFormProps) {
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const currentLogoUrl = publicProfile?.logo_url ?? null
  const [logoError, setLogoError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [publicName, setPublicName] = useState(publicProfile?.public_name ?? "")
  const [publicSummary, setPublicSummary] = useState(publicProfile?.public_summary ?? "")
  const [sector, setSector] = useState(publicProfile?.sector ?? "")
  const [technologies, setTechnologies] = useState((publicProfile?.technologies ?? []).join(", "))
  const [websiteUrl, setWebsiteUrl] = useState(publicProfile?.website_url ?? "")
  const [fundingVisibility, setFundingVisibility] = useState<ProjectVisibility>(
    publicProfile?.funding_visibility ?? "private",
  )
  const [complianceVisibility, setComplianceVisibility] = useState<ProjectVisibility>(
    publicProfile?.compliance_visibility ?? "private",
  )

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Aperçu local du fichier choisi, révoqué à chaque changement pour ne pas
  // accumuler des object URLs en mémoire tant que le formulaire reste ouvert.
  useEffect(() => {
    if (!logoFile) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(logoFile)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [logoFile])

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setLogoError(null)
    setLogoFile(e.target.files?.[0] ?? null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLogoError(null)

    // Upload Cloudinary seulement ici, avant le PATCH — pas au moment où le
    // fichier est choisi (voir docstring du composant).
    let logoUrl = currentLogoUrl
    setIsSubmitting(true)
    try {
      if (logoFile) {
        try {
          const result = await uploadProjectLogo(accessToken, projectId, logoFile)
          logoUrl = result.logo_url
        } catch (err) {
          setLogoError(err instanceof ApiError ? err.message : "Échec de l'upload du logo.")
          setIsSubmitting(false)
          return
        }
      }

      const payload: ProjectPublicProfileUpdate = {
        public_name: publicName.trim(),
        public_summary: publicSummary.trim(),
        sector: sector.trim(),
        technologies: parseList(technologies),
        website_url: websiteUrl.trim(),
        funding_visibility: fundingVisibility,
        compliance_visibility: complianceVisibility,
        ...(logoUrl !== null ? { logo_url: logoUrl } : {}),
      }

      await upsertPublicProfile(accessToken, projectId, payload)
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label className={labelClass}>Logo</label>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          className="hidden"
          id="update-logo-upload"
        />

        <div className="flex items-center gap-3">
          {previewUrl || currentLogoUrl ? (
            <img
              src={previewUrl ?? currentLogoUrl!}
              alt="Logo du projet"
              className="h-14 w-14 rounded-lg object-cover"
            />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-gray-100 text-xs text-gray-400">
              Logo
            </div>
          )}

          <div className="flex flex-1 flex-wrap items-center gap-2">
            <label
              htmlFor="update-logo-upload"
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:border-gray-400"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                className="h-4 w-4"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8.25 12 3.75m0 0L7.5 8.25M12 3.75v13.5"
                />
              </svg>
              Changer le logo
            </label>
            {logoFile && <span className="max-w-[10rem] truncate text-xs text-gray-500">{logoFile.name}</span>}
          </div>
        </div>
        <p className="text-xs text-gray-400">
          {logoFile ? "Envoyé à l'enregistrement." : "PNG, JPG — logo de ton projet."}
        </p>
        {logoError && <p className="text-xs text-red-600">{logoError}</p>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-public-name">
          Nom public
        </label>
        <input
          id="update-public-name"
          type="text"
          value={publicName}
          onChange={(e) => setPublicName(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-public-summary">
          Résumé public
        </label>
        <textarea
          id="update-public-summary"
          value={publicSummary}
          onChange={(e) => setPublicSummary(e.target.value)}
          rows={3}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-public-sector">
          Secteur (vitrine)
        </label>
        <input
          id="update-public-sector"
          type="text"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-public-technologies">
          Technologies (vitrine) <span className="font-normal text-gray-400">(séparées par des virgules)</span>
        </label>
        <input
          id="update-public-technologies"
          type="text"
          value={technologies}
          onChange={(e) => setTechnologies(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-website-url">
          Site web
        </label>
        <input
          id="update-website-url"
          type="text"
          value={websiteUrl}
          onChange={(e) => setWebsiteUrl(e.target.value)}
          className={inputClass}
        />
      </div>

      {/* Liste déroulante : valeurs imposées par le CheckConstraint ajouté en base
          (migration 82a64157b35d) — voir projectVisibilityOptions.ts. */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-funding-visibility">
            Visibilité — levée de fonds
          </label>
          <select
            id="update-funding-visibility"
            value={fundingVisibility}
            onChange={(e) => setFundingVisibility(e.target.value as ProjectVisibility)}
            className={inputClass}
          >
            {VISIBILITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-compliance-visibility">
            Visibilité — conformité
          </label>
          <select
            id="update-compliance-visibility"
            value={complianceVisibility}
            onChange={(e) => setComplianceVisibility(e.target.value as ProjectVisibility)}
            className={inputClass}
          >
            {VISIBILITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </form>
  )
}
