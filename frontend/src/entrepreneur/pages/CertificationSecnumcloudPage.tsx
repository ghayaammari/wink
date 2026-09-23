import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import ComplianceScoreBadge from "../components/compliance/ComplianceScoreBadge"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  getSecnumcloudEstimation,
  getSecnumcloudObligations,
  getSecnumcloudScore,
  runSecnumcloudDiagnostic,
  updateSecnumcloudObligationStatut,
  type ComplianceScoreRead,
  type ObligationStatut,
  type ProjectCertificationEstimationRead,
  type ProjectCertificationObligationRead,
} from "../api/certificationApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * Page de suivi SecNumCloud (service 3.3.11). Le bouton "Générer mon
 * parcours" appelle le 6e sous-agent de compliance_agent (agentic RAG sur le
 * corpus ANSSI, voir secnumcloud_diagnostic_service.py) -- ajouté le
 * 22/09/2026, quand cet agent a été construit (avant, cette page n'affichait
 * qu'un message "en attente", voir git blame). Même principe que
 * RgpdDiagnosticPage : génération explicite au clic, jamais automatique
 * (appel LLM coûteux).
 */
export default function CertificationSecnumcloudPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [obligations, setObligations] = useState<ProjectCertificationObligationRead[]>([])
  const [score, setScore] = useState<ComplianceScoreRead | null>(null)
  const [estimation, setEstimation] = useState<ProjectCertificationEstimationRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      const [obligationsList, scoreResult, estimationResult] = await Promise.all([
        getSecnumcloudObligations(accessToken, project.id),
        getSecnumcloudScore(accessToken, project.id),
        getSecnumcloudEstimation(accessToken, project.id),
      ])
      setObligations(obligationsList)
      setScore(scoreResult)
      setEstimation(estimationResult)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger le suivi SecNumCloud.")
      setState("error")
    })
  }, [accessToken])

  async function handleToggle(obligation: ProjectCertificationObligationRead) {
    if (!accessToken || !projectId) return
    const nextStatut: ObligationStatut = obligation.statut === "fait" ? "a_faire" : "fait"
    const updated = await updateSecnumcloudObligationStatut(accessToken, projectId, obligation.id, nextStatut)
    setObligations((current) => current.map((o) => (o.id === updated.id ? updated : o)))
    setScore(await getSecnumcloudScore(accessToken, projectId))
  }

  async function handleGenerer() {
    if (!accessToken || !projectId) return
    setGenerating(true)
    setError(null)
    try {
      const [obligationsList, estimationResult, scoreResult] = await Promise.all([
        runSecnumcloudDiagnostic(accessToken, projectId),
        getSecnumcloudEstimation(accessToken, projectId),
        getSecnumcloudScore(accessToken, projectId),
      ])
      setObligations(obligationsList)
      setEstimation(estimationResult)
      setScore(scoreResult)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la génération du parcours SecNumCloud.")
    } finally {
      setGenerating(false)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-gray-900">Certification SecNumCloud</h1>
        <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Certification SecNumCloud</h1>
        <p className="text-sm text-gray-500">
          Parcours, délai et coût estimés pour obtenir la qualification SecNumCloud (ANSSI), exigée par les marchés
          publics et les opérateurs d'importance vitale.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {score && <ComplianceScoreBadge score={score.score} totalObligations={score.total_obligations} />}

      {estimation && (
        <div className="flex flex-col gap-1 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <span className="text-sm font-medium text-gray-900">
            Délai estimé : {estimation.delai_mois_min}–{estimation.delai_mois_max} mois · Coût estimé :{" "}
            {estimation.cout_estime_min.toLocaleString("fr-FR")}–{estimation.cout_estime_max.toLocaleString("fr-FR")} €
          </span>
          <span className="text-xs text-gray-500">{estimation.justification}</span>
        </div>
      )}

      <button
        type="button"
        onClick={handleGenerer}
        disabled={generating}
        className="self-start rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {generating
          ? "Génération en cours..."
          : obligations.length === 0
            ? "Générer mon parcours"
            : "Régénérer mon parcours"}
      </button>

      {obligations.length === 0 ? (
        <p className="text-sm text-gray-500">
          Aucun parcours généré pour l'instant. Clique sur "Générer mon parcours" pour que l'agent conformité
          propose les étapes et estime le délai/coût à partir du référentiel ANSSI.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {obligations.map((obligation) => (
            <li key={obligation.id} className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
              <input
                type="checkbox"
                checked={obligation.statut === "fait"}
                onChange={() => handleToggle(obligation)}
                className="mt-1"
              />
              <div className="flex flex-col">
                <span
                  className={`text-sm font-medium ${
                    obligation.statut === "fait" ? "text-gray-400 line-through" : "text-gray-900"
                  }`}
                >
                  {obligation.ordre}. {obligation.nom}
                </span>
                <span className="text-xs text-gray-500">{obligation.description}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
