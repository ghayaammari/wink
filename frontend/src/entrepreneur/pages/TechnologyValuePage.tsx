import { type FormEvent, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { updateProject } from "../api/projectApi"
import { ExtractedFieldFrame } from "../components/ExtractedFieldFrame"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"
import { useDraftSync } from "../hooks/useDraftSync"
import { useExtractedFieldTracking } from "../hooks/useExtractedFieldTracking"
import {
  extractedListText,
  extractedText,
  initialFieldValue,
} from "../utils/extractedFieldValue"
import { clearDraft, readDraft } from "../utils/formDraft"

const FIELD_TECHNOLOGIES = "projects.technologies"
const FIELD_VALUE_PROPOSITION = "projects.value_proposition"

function toList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

interface Draft {
  technologies: string
  valueProposition: string
}

/** Écran 7 — "Ce qui rend votre projet unique" (service 0.0.3). */
export default function TechnologyValuePage() {
  const { project, setProject, fieldValues, goNext, goPrevious } =
    useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [
    FIELD_TECHNOLOGIES,
    FIELD_VALUE_PROPOSITION,
  ])
  const draft = project
    ? readDraft<Draft>(project.id, "technology_value")
    : null

  const [technologies, setTechnologies] = useState(
    () =>
      draft?.technologies ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_TECHNOLOGIES,
        extractedListText,
        project?.technologies.join(", ") ?? "",
      ),
  )
  const [valueProposition, setValueProposition] = useState(
    () =>
      draft?.valueProposition ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_VALUE_PROPOSITION,
        extractedText,
        project?.value_proposition ?? "",
      ),
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useDraftSync(
    project?.id,
    "technology_value",
    { technologies, valueProposition },
    !isSubmitting,
  )

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      const updated = await updateProject(accessToken, project.id, {
        technologies: toList(technologies),
        value_proposition: valueProposition || undefined,
        resolved_field_values: tracking.buildResolutions(),
      })
      setProject(updated)
      clearDraft(project.id, "technology_value")
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
        active={tracking.isActive(FIELD_TECHNOLOGIES)}
        touched={tracking.isTouched(FIELD_TECHNOLOGIES)}
        onIgnore={() => tracking.ignore(FIELD_TECHNOLOGIES)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Quelles technologies utilisez-vous ou prévoyez-vous d'utiliser ?
          </label>
          <input
            type="text"
            value={technologies}
            onChange={(e) => {
              setTechnologies(e.target.value)
              tracking.markTouched(FIELD_TECHNOLOGIES)
            }}
            placeholder="Séparées par des virgules"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_VALUE_PROPOSITION)}
        touched={tracking.isTouched(FIELD_VALUE_PROPOSITION)}
        onIgnore={() => tracking.ignore(FIELD_VALUE_PROPOSITION)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            En une phrase, quelle est votre proposition de valeur ?
          </label>
          <textarea
            value={valueProposition}
            onChange={(e) => {
              setValueProposition(e.target.value)
              tracking.markTouched(FIELD_VALUE_PROPOSITION)
            }}
            rows={3}
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
