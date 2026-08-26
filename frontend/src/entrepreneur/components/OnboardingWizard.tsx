import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject, type ProjectRead } from "../api/projectApi"
import { WIZARD_STEP_LABELS, type WizardStep, useOnboardingWizard } from "../context/OnboardingWizardContext"
import LegalProfilePage from "../pages/LegalProfilePage"
import LocationPage from "../pages/LocationPage"
import ProjectDescriptionPage from "../pages/ProjectDescriptionPage"
import ProjectStagePage from "../pages/ProjectStagePage"
import PublicProfilePage from "../pages/PublicProfilePage"
import RecapPage from "../pages/RecapPage"
import SectorMarketPage from "../pages/SectorMarketPage"
import TeamFundingPage from "../pages/TeamFundingPage"
import TechnologyValuePage from "../pages/TechnologyValuePage"
import CircularProgress from "./CircularProgress"
import StepIndicator from "./StepIndicator"

const STEP_COMPONENTS: Record<WizardStep, React.ComponentType> = {
  stage: ProjectStagePage,
  legal: LegalProfilePage,
  description: ProjectDescriptionPage,
  sector_market: SectorMarketPage,
  team_funding: TeamFundingPage,
  technology_value: TechnologyValuePage,
  location: LocationPage,
  public: PublicProfilePage,
  recap: RecapPage,
}

/** Simplification assumée pour I0 : ProjectRead n'embarque pas l'état de
 * project_legal_profiles / project_public_profiles (des tables séparées), donc
 * la reprise ne sait précisément où en sont QUE les écrans dont les champs
 * vivent directement sur `projects` (description, secteur, équipe,
 * technologie, localisation). Revenir sur l'écran légal ou vitrine publique
 * déjà rempli est sans risque : les deux endpoints concernés gèrent le
 * doublon / l'upsert proprement (voir LegalProfilePage, PublicProfilePage).
 *
 * Deuxième approximation assumée : les écrans 5 à 8 ont des champs facultatifs
 * (voir tableau récapitulatif du questionnaire — seuls "Obligatoire : Oui" sont
 * 1-4). Un champ resté vide peut donc signifier "pas encore vu cet écran" ou
 * "vu, volontairement laissé vide" — on ne distingue pas les deux, on reprend
 * simplement au premier écran dont TOUS les champs sont encore vides. */
function determineResumeStep(project: ProjectRead, steps: WizardStep[]): WizardStep {
  if (project.description === null) {
    return steps.includes("legal") ? "legal" : "description"
  }
  if (project.sector === null && project.subsectors.length === 0) {
    return "sector_market"
  }
  if (project.nombre_cofondateurs === null && project.intention_levee_fonds === null) {
    return "team_funding"
  }
  if (project.technologies.length === 0 && project.value_proposition === null) {
    return "technology_value"
  }
  if (project.localisation === null) {
    return "location"
  }
  if (project.project_profile_completion === "complet") {
    return "recap"
  }
  return "public"
}

/** Orchestrateur du wizard — voir OnboardingWizardContext.tsx pour ce que
 * signifie "wizard" ici. Ce composant ne connaît que l'ordre des écrans, pas
 * leur contenu individuel. */
export default function OnboardingWizard() {
  const { project, setProject, currentStep, goToStep, steps } = useOnboardingWizard()
  const { accessToken } = useAuth()
  const [isLoading, setIsLoading] = useState(project === null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (project !== null || !accessToken) {
      setIsLoading(false)
      return
    }
    // Cas d'une arrivée directe sur /onboarding (rechargement de page en plein
    // wizard) : le contexte est vide, on récupère le projet existant côté API
    // pour reprendre au bon écran plutôt que de repartir de zéro.
    getMyProject(accessToken)
      .then((existingProject) => {
        if (existingProject) {
          setProject(existingProject)
          goToStep(determineResumeStep(existingProject, steps))
        }
      })
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Impossible de charger ton projet.")
      })
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [])

  if (isLoading) {
    return <p className="text-center text-sm text-gray-500">Chargement...</p>
  }

  if (error) {
    return <p className="text-center text-sm text-red-600">{error}</p>
  }

  const StepComponent = STEP_COMPONENTS[currentStep]

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4 py-12">
      <StepIndicator />
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-gray-900">{WIZARD_STEP_LABELS[currentStep]}</h2>
        <CircularProgress percentage={project?.completion_percentage ?? 0} />
      </div>
      <StepComponent />
    </div>
  )
}
