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

const FIELD_SECTOR = "projects.sector"
const FIELD_SUBSECTORS = "projects.subsectors"
const FIELD_CUSTOMER_SEGMENTS = "projects.customer_segments"
const FIELD_TARGET_USERS = "projects.target_users"

function toList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

interface Draft {
  sector: string
  subsectors: string
  customerSegments: string
  targetUsers: string
}

/** Écran 5 — "Votre secteur d'activité" (service 0.0.3). Non obligatoire :
 * les champs à tags peuvent rester vides (voir tableau récapitulatif du
 * questionnaire), d'où l'absence de `required` sur les inputs. */
export default function SectorMarketPage() {
  const { project, setProject, fieldValues, goNext, goPrevious } =
    useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [
    FIELD_SECTOR,
    FIELD_SUBSECTORS,
    FIELD_CUSTOMER_SEGMENTS,
    FIELD_TARGET_USERS,
  ])
  const draft = project ? readDraft<Draft>(project.id, "sector_market") : null

  const [sector, setSector] = useState(
    () =>
      draft?.sector ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_SECTOR,
        extractedText,
        project?.sector ?? "",
      ),
  )
  const [subsectors, setSubsectors] = useState(
    () =>
      draft?.subsectors ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_SUBSECTORS,
        extractedListText,
        project?.subsectors.join(", ") ?? "",
      ),
  )
  const [customerSegments, setCustomerSegments] = useState(
    () =>
      draft?.customerSegments ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_CUSTOMER_SEGMENTS,
        extractedListText,
        project?.customer_segments.join(", ") ?? "",
      ),
  )
  const [targetUsers, setTargetUsers] = useState(
    () =>
      draft?.targetUsers ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_TARGET_USERS,
        extractedListText,
        project?.target_users.join(", ") ?? "",
      ),
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useDraftSync(
    project?.id,
    "sector_market",
    { sector, subsectors, customerSegments, targetUsers },
    !isSubmitting,
  )

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      const updated = await updateProject(accessToken, project.id, {
        sector: sector || undefined,
        subsectors: toList(subsectors),
        customer_segments: toList(customerSegments),
        target_users: toList(targetUsers),
        resolved_field_values: tracking.buildResolutions(),
      })
      setProject(updated)
      clearDraft(project.id, "sector_market")
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
        active={tracking.isActive(FIELD_SECTOR)}
        touched={tracking.isTouched(FIELD_SECTOR)}
        onIgnore={() => tracking.ignore(FIELD_SECTOR)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Quel est votre secteur d'activité ?
          </label>
          <input
            type="text"
            value={sector}
            onChange={(e) => {
              setSector(e.target.value)
              tracking.markTouched(FIELD_SECTOR)
            }}
            placeholder="Ex: Fintech"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_SUBSECTORS)}
        touched={tracking.isTouched(FIELD_SUBSECTORS)}
        onIgnore={() => tracking.ignore(FIELD_SUBSECTORS)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Y a-t-il des sous-secteurs qui vous concernent ?
          </label>
          <input
            type="text"
            value={subsectors}
            onChange={(e) => {
              setSubsectors(e.target.value)
              tracking.markTouched(FIELD_SUBSECTORS)
            }}
            placeholder="Séparés par des virgules"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_CUSTOMER_SEGMENTS)}
        touched={tracking.isTouched(FIELD_CUSTOMER_SEGMENTS)}
        onIgnore={() => tracking.ignore(FIELD_CUSTOMER_SEGMENTS)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Qui sont vos segments clients visés ?
          </label>
          <input
            type="text"
            value={customerSegments}
            onChange={(e) => {
              setCustomerSegments(e.target.value)
              tracking.markTouched(FIELD_CUSTOMER_SEGMENTS)
            }}
            placeholder="Séparés par des virgules"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_TARGET_USERS)}
        touched={tracking.isTouched(FIELD_TARGET_USERS)}
        onIgnore={() => tracking.ignore(FIELD_TARGET_USERS)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Qui sont vos utilisateurs cibles ?
          </label>
          <input
            type="text"
            value={targetUsers}
            onChange={(e) => {
              setTargetUsers(e.target.value)
              tracking.markTouched(FIELD_TARGET_USERS)
            }}
            placeholder="Séparés par des virgules"
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
