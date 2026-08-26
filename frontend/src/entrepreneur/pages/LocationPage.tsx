import { type FormEvent, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { updateProject } from "../api/projectApi"
import { ExtractedFieldFrame } from "../components/ExtractedFieldFrame"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"
import { useDraftSync } from "../hooks/useDraftSync"
import { useExtractedFieldTracking } from "../hooks/useExtractedFieldTracking"
import { extractedText, initialFieldValue } from "../utils/extractedFieldValue"
import { clearDraft, readDraft } from "../utils/formDraft"

const FIELD_LOCALISATION = "projects.localisation"

interface Draft {
  localisation: string
}

/** Écran 8 — "Où êtes-vous basé ?" (service 0.0.3), un seul champ. */
export default function LocationPage() {
  const { project, setProject, fieldValues, goNext, goPrevious } =
    useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [FIELD_LOCALISATION])
  const draft = project ? readDraft<Draft>(project.id, "location") : null

  const [localisation, setLocalisation] = useState(
    () =>
      draft?.localisation ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_LOCALISATION,
        extractedText,
        project?.localisation ?? "",
      ),
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useDraftSync(project?.id, "location", { localisation }, !isSubmitting)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      const updated = await updateProject(accessToken, project.id, {
        localisation: localisation || undefined,
        resolved_field_values: tracking.buildResolutions(),
      })
      setProject(updated)
      clearDraft(project.id, "location")
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
      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_LOCALISATION)}
        touched={tracking.isTouched(FIELD_LOCALISATION)}
        onIgnore={() => tracking.ignore(FIELD_LOCALISATION)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Dans quelle ville ou région êtes-vous situé ?
          </label>
          <input
            type="text"
            value={localisation}
            onChange={(e) => {
              setLocalisation(e.target.value)
              tracking.markTouched(FIELD_LOCALISATION)
            }}
            placeholder="Ex: Paris"
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
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Continuer"}
        </button>
      </div>
    </form>
  )
}
