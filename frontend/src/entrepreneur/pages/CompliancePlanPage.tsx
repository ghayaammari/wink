import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { getAiActScore } from "../api/aiActApi"
import { getMyProject, type ProjectRead } from "../api/projectApi"
import { getRgpdScore } from "../api/rgpdApi"
import { getFintechGapAnalysisScore, getHealthtechGapAnalysisScore, getSectorDetection } from "../api/sectorApi"
import { getSecnumcloudScore } from "../api/certificationApi"
import ProjectSectionCard from "../components/ProjectSectionCard"

function ICON_SHIELD_HEADER({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path
        d="M10 2.5l6 2.2v4.4c0 4-2.5 7-6 8.4-3.5-1.4-6-4.4-6-8.4V4.7l6-2.2z"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M7.5 10l1.8 1.8 3.2-3.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

type LoadState = "loading" | "ready" | "error"

/**
 * Deuxième "plan d'action" — landing EPIC-03 (Conformité & Normes
 * réglementaires). Distinct de PlanActionPage (EPIC-01, roadmap de création
 * pré-startup) : contenu et condition d'affichage différents, donc fichier
 * séparé plutôt qu'une variante de la même page (voir Wink_architecture_fichiers.md).
 *
 * Quatre cards à ce jour : RGPD (service 3.3.1), AI Act (service 3.3.12,
 * ajouté le 19/09/2026), Conformité sectorielle (service 3.3.5, HealthTech
 * + FinTech uniquement, ajouté le 19/09/2026) et Certification SecNumCloud
 * (service 3.3.11, V1 limitée a SecNumCloud, ajoutée le 21/09/2026). Les
 * autres services d'EPIC-03 (DPO, AIPD, gap analysis, ISO 27001/SOC 2...) ne
 * sont volontairement PAS affichés en cards désactivées "à venir" — ça
 * ajouterait de la structure UI pour des services qui n'existent pas encore
 * côté backend, sans bénéfice avant qu'ils soient réellement construits. La
 * card SecNumCloud respecte cette règle : le service backend existe déjà
 * (obligations + score, voir certification_router.py), même si la
 * génération automatique du parcours (6e sous-agent compliance_agent)
 * arrive dans une prochaine mise à jour -- score simplement `null` tant
 * qu'aucun parcours n'est généré, comme pour un secteur non détecté.
 * Ajouter la card suivante ici quand son service sera prêt, même pattern
 * que ProjectSectionCard.
 *
 * Chaque card affiche son score de conformité (% d'obligations "fait"/
 * accomplies) directement ici, sans attendre d'ouvrir le diagnostic —
 * demande explicite du 20/09/2026. La card "Conformité sectorielle" montre
 * le score du secteur détecté (HealthTech OU FinTech, jamais les deux) :
 * pas de score tant qu'aucun secteur n'est détecté. `null` (pas encore de
 * diagnostic généré) -> aucun badge, voir ProjectSectionCard/ComplianceScoreBadge.
 *
 * Pas de condition sur project_type (contrairement à PlanActionPage) : la
 * conformité RGPD s'applique à tout projet traitant des données, que la
 * startup soit déjà créée ou non.
 */
export default function CompliancePlanPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rgpdScorePercent, setRgpdScorePercent] = useState<number | null>(null)
  const [aiActScorePercent, setAiActScorePercent] = useState<number | null>(null)
  const [sectorScorePercent, setSectorScorePercent] = useState<number | null>(null)
  const [secnumcloudScorePercent, setSecnumcloudScorePercent] = useState<number | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const current = await getMyProject(accessToken)
      setProject(current)
      if (!current) {
        setState("ready")
        return
      }
      // Les 3 scores sont indépendants les uns des autres : un échec sur l'un
      // ne doit pas empêcher d'afficher les 2 autres. RGPD/AI Act toujours
      // interrogeables (tout projet peut avoir un diagnostic) ; le score
      // sectoriel dépend d'abord du secteur détecté.
      const [rgpdScore, aiActScore, detection, secnumcloudScore] = await Promise.all([
        getRgpdScore(accessToken, current.id),
        getAiActScore(accessToken, current.id),
        getSectorDetection(accessToken, current.id),
        getSecnumcloudScore(accessToken, current.id),
      ])
      setRgpdScorePercent(rgpdScore.score)
      setAiActScorePercent(aiActScore.score)
      setSecnumcloudScorePercent(secnumcloudScore.score)

      if (detection.secteur_detecte === "healthtech") {
        setSectorScorePercent((await getHealthtechGapAnalysisScore(accessToken, current.id)).score)
      } else if (detection.secteur_detecte === "fintech") {
        setSectorScorePercent((await getFintechGapAnalysisScore(accessToken, current.id)).score)
      }
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger le plan de conformité.")
      setState("error")
    })
  }, [accessToken])

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (!project) {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-gray-900">Conformité</h1>
        <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
          <ICON_SHIELD_HEADER />
        </div>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold text-gray-900">Conformité</h1>
          <p className="text-sm text-gray-500">Diagnostics et obligations réglementaires applicables à ton projet.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ProjectSectionCard
          to="/entrepreneur/conformite/rgpd"
          title="Diagnostic RGPD"
          description="Réponds à quelques questions sur tes données personnelles pour obtenir tes obligations"
          pendingCount={0}
          scorePercent={rgpdScorePercent}
        />
        <ProjectSectionCard
          to="/entrepreneur/conformite/ai-act"
          title="Diagnostic AI Act"
          description="Réponds à quelques questions sur ton usage de l'IA pour obtenir ta catégorie de risque et tes obligations"
          pendingCount={0}
          scorePercent={aiActScorePercent}
        />
        <ProjectSectionCard
          to="/entrepreneur/conformite/secteur"
          title="Conformité sectorielle"
          description="Détecte si ton projet relève de la HealthTech ou de la FinTech pour obtenir ta classification réglementaire"
          pendingCount={0}
          scorePercent={sectorScorePercent}
        />
        <ProjectSectionCard
          to="/entrepreneur/conformite/certification-secnumcloud"
          title="Certification SecNumCloud"
          description="Suis ton parcours vers la qualification SecNumCloud (ANSSI), exigée pour vendre à l'État"
          pendingCount={0}
          scorePercent={secnumcloudScorePercent}
        />
      </div>
    </div>
  )
}
