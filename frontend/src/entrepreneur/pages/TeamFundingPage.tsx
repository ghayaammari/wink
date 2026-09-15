import { type FormEvent, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { updateProject } from "../api/projectApi"
import { ExtractedFieldFrame } from "../components/ExtractedFieldFrame"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"
import { useDraftSync } from "../hooks/useDraftSync"
import { useExtractedFieldTracking } from "../hooks/useExtractedFieldTracking"
import {
  extractedBoolean,
  extractedNumberText,
  initialFieldValue,
} from "../utils/extractedFieldValue"
import { clearDraft, readDraft } from "../utils/formDraft"
import { IMMEDIATE_OBJECTIVES } from "../utils/projectImmediateObjectives"

const FIELD_NOMBRE_COFONDATEURS = "projects.nombre_cofondateurs"
const FIELD_INTENTION_LEVEE_FONDS = "projects.intention_levee_fonds"

const FUNDING_OPTIONS: { value: boolean | null; label: string }[] = [
  { value: true, label: "Oui" },
  { value: false, label: "Non" },
  { value: null, label: "Pas encore décidé" },
]

interface Draft {
  nombreCofondateurs: string
  intentionLeveeFonds: boolean | null
  objectifsImmediats: string[]
}

/** Écran 6 — "Votre équipe et vos ambitions" (service 0.0.3). Le questionnaire
 * demande 3 réponses possibles pour la levée de fonds (Oui / Non / Pas encore
 * décidé), alors que `projects.intention_levee_fonds` est un simple booléen
 * nullable — "Pas encore décidé" et "pas répondu" partagent donc la même
 * valeur NULL en base, il n'y a pas de 3ᵉ état distinct à stocker.
 *
 * Champ à boutons (pas un input texte) : le cadre `ExtractedFieldFrame`
 * encadre tout le groupe de boutons plutôt qu'un bouton précis — Ignorer
 * s'applique au champ, pas à une option. N'importe quel clic marque le champ
 * "touché", même en re-sélectionnant l'option déjà pré-remplie par
 * l'extraction. */
export default function TeamFundingPage() {
  const { project, setProject, fieldValues, goNext, goPrevious } =
    useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [
    FIELD_NOMBRE_COFONDATEURS,
    FIELD_INTENTION_LEVEE_FONDS,
  ])
  const draft = project ? readDraft<Draft>(project.id, "team_funding") : null

  const [nombreCofondateurs, setNombreCofondateurs] = useState(
    () =>
      draft?.nombreCofondateurs ??
      initialFieldValue(
        tracking.pendingByField,
        FIELD_NOMBRE_COFONDATEURS,
        extractedNumberText,
        project?.nombre_cofondateurs?.toString() ?? "",
      ),
  )
  const [intentionLeveeFonds, setIntentionLeveeFonds] = useState<
    boolean | null
  >(() =>
    draft
      ? draft.intentionLeveeFonds
      : initialFieldValue(
          tracking.pendingByField,
          FIELD_INTENTION_LEVEE_FONDS,
          extractedBoolean,
          project?.intention_levee_fonds ?? null,
        ),
  )
  const [objectifsImmediats, setObjectifsImmediats] = useState<string[]>(
    () => draft?.objectifsImmediats ?? project?.objectifs_immediats ?? [],
  )
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useDraftSync(
    project?.id,
    "team_funding",
    { nombreCofondateurs, intentionLeveeFonds, objectifsImmediats },
    !isSubmitting,
  )

  function toggleObjectif(code: string) {
    setObjectifsImmediats((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    )
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      const updated = await updateProject(accessToken, project.id, {
        nombre_cofondateurs: nombreCofondateurs
          ? Number(nombreCofondateurs)
          : undefined,
        intention_levee_fonds: intentionLeveeFonds ?? undefined,
        // Liste complète (pas un diff) : une liste vide efface les objectifs posés
        // lors d'un passage précédent. (réalisé par OPENCODE)
        objectifs_immediats: objectifsImmediats,
        resolved_field_values: tracking.buildResolutions(),
      })
      setProject(updated)
      clearDraft(project.id, "team_funding")
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
        active={tracking.isActive(FIELD_NOMBRE_COFONDATEURS)}
        touched={tracking.isTouched(FIELD_NOMBRE_COFONDATEURS)}
        onIgnore={() => tracking.ignore(FIELD_NOMBRE_COFONDATEURS)}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Combien de cofondateurs avez-vous ?
          </label>
          <input
            type="number"
            min={0}
            value={nombreCofondateurs}
            onChange={(e) => {
              setNombreCofondateurs(e.target.value)
              tracking.markTouched(FIELD_NOMBRE_COFONDATEURS)
            }}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </ExtractedFieldFrame>

      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_INTENTION_LEVEE_FONDS)}
        touched={tracking.isTouched(FIELD_INTENTION_LEVEE_FONDS)}
        onIgnore={() => tracking.ignore(FIELD_INTENTION_LEVEE_FONDS)}
      >
        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">
            Envisagez-vous de lever des fonds ?
          </p>
          <div className="grid grid-cols-3 gap-2">
            {FUNDING_OPTIONS.map((option) => (
              <button
                key={option.label}
                type="button"
                onClick={() => {
                  setIntentionLeveeFonds(option.value)
                  tracking.markTouched(FIELD_INTENTION_LEVEE_FONDS)
                }}
                className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                  intentionLeveeFonds === option.value
                    ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                    : "border-gray-300 text-gray-700 hover:border-gray-400"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </ExtractedFieldFrame>

      {/* Écran 6 — objectifs immédiats (question ajoutée pour le filtrage de la
        roadmap, service 1.1.11). Sert uniquement au filtrage, ne compte pas
        dans le pourcentage de complétion du profil. (réalisé par OPENCODE) */}
      <div>
        <p className="mb-2 text-sm font-medium text-gray-700">
          Quels sont vos objectifs immédiats ?
        </p>
        <div className="flex flex-col gap-2">
          {IMMEDIATE_OBJECTIVES.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition hover:border-gray-400"
            >
              <input
                type="checkbox"
                checked={objectifsImmediats.includes(option.value)}
                onChange={() => toggleObjectif(option.value)}
                className="h-4 w-4"
              />
              {option.label}
            </label>
          ))}
        </div>
      </div>

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
