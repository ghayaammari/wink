import { useNavigate } from "react-router-dom"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"

const STAGE_LABELS: Record<string, string> = {
  ideation: "Idéation",
  pre_seed: "Pré-amorçage",
  seed: "Amorçage",
  serie_a: "Série A",
}

/** Écran 10 — récapitulatif final, fin du questionnaire d'onboarding. */
export default function RecapPage() {
  const { project } = useOnboardingWizard()
  const navigate = useNavigate()

  if (!project) return null

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-gray-500">
        Ton profil est {project.project_profile_completion === "complet" ? "complet" : "prêt"} — tu pourras toujours
        compléter les informations manquantes plus tard depuis ton profil.
      </p>

      <dl className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 text-sm">
        <div className="flex justify-between">
          <dt className="text-gray-500">Stade</dt>
          <dd className="font-medium text-gray-900">{STAGE_LABELS[project.stage]}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Secteur</dt>
          <dd className="font-medium text-gray-900">{project.sector ?? "—"}</dd>
        </div>
        <div>
          <dt className="mb-1 text-gray-500">Description</dt>
          <dd className="text-gray-900">{project.description ?? "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-500">Complétion</dt>
          <dd className="font-medium text-gray-900">{project.completion_percentage}%</dd>
        </div>
      </dl>

      <button
        type="button"
        onClick={() => navigate("/")}
        className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
      >
        Accéder à mon espace
      </button>
    </div>
  )
}
