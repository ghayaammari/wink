/**
 * État partagé du questionnaire d'onboarding (services 0.0.2, 0.0.3, 0.0.4) — le
 * projet en cours de construction et l'écran actuel, accessibles par tous les
 * écrans enfants sans prop drilling ni refetch à chaque étape.
 *
 * Remarque — "wizard" : terme UI standard (pas de traduction figée en français)
 * pour un parcours en plusieurs étapes séquentielles guidées, où chaque écran
 * dépend souvent des réponses précédentes (ex: l'écran légal n'existe que si
 * project_type = "created"), avec une notion de progression affichée à
 * l'utilisateur. Même idée qu'un assistant d'installation "suivant, suivant,
 * terminer". Rien de plus qu'un nom de convention — pas un concept technique.
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react"
import type { ProjectFieldValueRead, ProjectRead } from "../api/projectApi"

export type WizardStep =
  | "stage"
  | "legal"
  | "description"
  | "sector_market"
  | "team_funding"
  | "technology_value"
  | "location"
  | "public"
  | "recap"

interface OnboardingWizardContextValue {
  /** Le projet en cours de construction — null tant que l'écran 2 n'a pas encore
   * appelé POST /projects. */
  project: ProjectRead | null
  setProject: (project: ProjectRead) => void
  /** Champs extraits d'un document importé (Écran 4, chemin B), en attente ou
   * déjà résolus — vide tant qu'aucun document n'a été importé. Même pattern
   * que `project`/`setProject` : le contexte ne fait aucun appel API lui-même,
   * chaque écran fetch et pousse ici (voir ProjectDescriptionPage.tsx). */
  fieldValues: ProjectFieldValueRead[]
  setFieldValues: (fieldValues: ProjectFieldValueRead[]) => void
  /** Ordre des écrans pour CE projet — "legal" est retiré dynamiquement si
   * project_type = "not_created" (voir docstring update_project côté backend :
   * un écran sauté n'est pas compté comme manquant dans le calcul de complétion). */
  steps: WizardStep[]
  currentStep: WizardStep
  goToStep: (step: WizardStep) => void
  goNext: () => void
  goPrevious: () => void
  isFirstStep: boolean
  isLastStep: boolean
}

const ALL_STEPS: WizardStep[] = [
  "stage",
  "legal",
  "description",
  "sector_market",
  "team_funding",
  "technology_value",
  "location",
  "public",
  "recap",
]

/** Titre affiché par écran — repris tel quel du questionnaire Notion
 * ("Wink — Questionnaire d'onboarding Entrepreneur"), pas une reformulation
 * maison. Source unique utilisée par `OnboardingWizard` pour le titre de page,
 * pour ne jamais désynchroniser le libellé entre plusieurs endroits de l'UI. */
export const WIZARD_STEP_LABELS: Record<WizardStep, string> = {
  stage: "Parlons de votre projet",
  legal: "Quelques informations sur votre société",
  description: "Décrivez votre projet",
  sector_market: "Votre secteur d'activité",
  team_funding: "Votre équipe et vos ambitions",
  technology_value: "Ce qui rend votre projet unique",
  location: "Où êtes-vous basé ?",
  public: "Votre image publique (facultatif)",
  recap: "Votre profil",
}

const OnboardingWizardContext = createContext<OnboardingWizardContextValue | undefined>(undefined)

export function OnboardingWizardProvider({ children }: { children: ReactNode }) {
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [fieldValues, setFieldValues] = useState<ProjectFieldValueRead[]>([])
  const [stepIndex, setStepIndex] = useState(0)

  const steps = useMemo<WizardStep[]>(() => {
    if (project?.project_type === "not_created") {
      return ALL_STEPS.filter((step) => step !== "legal")
    }
    return ALL_STEPS
  }, [project?.project_type])

  const currentStep = steps[Math.min(stepIndex, steps.length - 1)]

  function goToStep(step: WizardStep) {
    const index = steps.indexOf(step)
    if (index !== -1) setStepIndex(index)
  }

  function goNext() {
    setStepIndex((i) => Math.min(i + 1, steps.length - 1))
  }

  function goPrevious() {
    setStepIndex((i) => Math.max(i - 1, 0))
  }

  const value: OnboardingWizardContextValue = {
    project,
    setProject,
    fieldValues,
    setFieldValues,
    steps,
    currentStep,
    goToStep,
    goNext,
    goPrevious,
    isFirstStep: stepIndex === 0,
    isLastStep: stepIndex === steps.length - 1,
  }

  return <OnboardingWizardContext.Provider value={value}>{children}</OnboardingWizardContext.Provider>
}

export function useOnboardingWizard(): OnboardingWizardContextValue {
  const ctx = useContext(OnboardingWizardContext)
  if (!ctx) {
    throw new Error("useOnboardingWizard doit être utilisé à l'intérieur d'un <OnboardingWizardProvider>.")
  }
  return ctx
}
