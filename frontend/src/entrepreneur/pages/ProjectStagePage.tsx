import { type FormEvent, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { createProject, type ProjectStage, type ProjectType } from "../api/projectApi"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"

/** Les stades proposés dépendent de la réponse à la première question : une
 * startup "pas encore créée" ne peut être qu'en idéation ou pré-amorçage, une
 * startup "déjà créée" a au minimum passé le pré-amorçage (immatriculée). */
const STAGE_OPTIONS_BY_TYPE: Record<ProjectType, { value: ProjectStage; label: string }[]> = {
  not_created: [
    { value: "ideation", label: "Idéation" },
    { value: "pre_seed", label: "Pré-amorçage" },
  ],
  created: [
    { value: "pre_seed", label: "Pré-amorçage" },
    { value: "seed", label: "Amorçage" },
    { value: "serie_a", label: "Série A" },
  ],
}

/** Écran 2 — service 0.0.2 : project_type + stage, seuls champs demandés à la
 * création du projet (description/source_type arrivent à l'écran 4). */
export default function ProjectStagePage() {
  const [projectType, setProjectType] = useState<ProjectType | null>(null)
  const [stage, setStage] = useState<ProjectStage | "">("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { accessToken } = useAuth()
  const { setProject, goNext } = useOnboardingWizard()

  function handleProjectTypeChange(newType: ProjectType) {
    setProjectType(newType)
    // Le stade choisi peut ne plus être valide pour le nouveau type (ex: passer
    // de "créée" à "pas encore créée" alors que "Série A" était sélectionné) —
    // on le réinitialise plutôt que de laisser une valeur incohérente.
    setStage("")
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!projectType || !stage || !accessToken) return

    setError(null)
    setIsSubmitting(true)
    try {
      const project = await createProject(accessToken, { project_type: projectType, stage })
      setProject(project)
      goNext()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <div>
        <p className="mb-2 text-sm font-medium text-gray-700">Ta startup est-elle déjà immatriculée ?</p>
        <div className="grid grid-cols-2 gap-2">
          {(
            [
              { value: "not_created", label: "Pas encore créée" },
              { value: "created", label: "Déjà créée" },
            ] as const
          ).map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => handleProjectTypeChange(option.value)}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                projectType === option.value
                  ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                  : "border-gray-300 text-gray-700 hover:border-gray-400"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {projectType && (
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">À quel stade financier vous situez-vous ?</label>
          <select
            value={stage}
            onChange={(e) => setStage(e.target.value as ProjectStage)}
            required
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          >
            <option value="" disabled>
              Sélectionner...
            </option>
            {STAGE_OPTIONS_BY_TYPE[projectType].map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={!projectType || !stage || isSubmitting}
        className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
      >
        {isSubmitting ? "Enregistrement..." : "Continuer"}
      </button>
    </form>
  )
}
