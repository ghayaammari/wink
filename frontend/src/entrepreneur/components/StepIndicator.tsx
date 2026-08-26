import { Fragment } from "react"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"

/** Repères numérotés (1 -- 2 -- 3 -- 4...) en haut du wizard : distinct de
 * `CircularProgress`, qui montre le % de champs remplis (donnée métier,
 * calculée côté backend). Ici c'est une jauge de NAVIGATION — où en est
 * l'utilisateur dans la liste des écrans, indépendamment de ce qu'il a rempli
 * ou non. Le titre de chaque écran est affiché séparément par `OnboardingWizard`
 * (voir WIZARD_STEP_LABELS) — pas de texte "Étape X/N" ici, juste les repères. */
export default function StepIndicator() {
  const { steps, currentStep } = useOnboardingWizard()
  const currentIndex = steps.indexOf(currentStep)

  return (
    <div className="flex items-center">
      {steps.map((step, index) => {
        const isDone = index < currentIndex
        const isCurrent = index === currentIndex

        return (
          <Fragment key={step}>
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-medium transition ${
                isDone
                  ? "bg-indigo-600 text-white"
                  : isCurrent
                    ? "border-2 border-indigo-600 text-indigo-700"
                    : "border border-gray-300 text-gray-400"
              }`}
            >
              {isDone ? "✓" : index + 1}
            </div>
            {index < steps.length - 1 && (
              <div className={`h-px flex-1 ${isDone ? "bg-indigo-600" : "bg-gray-200"}`} />
            )}
          </Fragment>
        )
      })}
    </div>
  )
}
