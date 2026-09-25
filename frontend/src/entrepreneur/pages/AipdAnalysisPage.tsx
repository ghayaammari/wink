import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { generateAipdAnalysis, getAipdAnalyses, type AipdAnalysisRead } from "../api/aipdApi"
import { getMyProject } from "../api/projectApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * Détail du service 3.3.4 (générateur d'AIPD) — ouverte depuis le bouton
 * "Faire mon AIPD" de RgpdDiagnosticPage. Fichier séparé de
 * RgpdDiagnosticPage.tsx (responsabilité différente : génération, pas
 * diagnostic — même règle que côté backend, voir aipd_router.py).
 *
 * Chaque génération crée une nouvelle ligne dans `aipd_analyses` (pas
 * d'édition d'une analyse existante, voir docstring backend
 * aipd_analysis_service.py) : l'historique complet est affiché, la plus
 * récente en premier.
 */
export default function AipdAnalysisPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [analyses, setAnalyses] = useState<AipdAnalysisRead[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      const currentAnalyses = await getAipdAnalyses(accessToken, project.id)
      setAnalyses(currentAnalyses)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger les analyses d'impact.")
      setState("error")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de token
  }, [accessToken])

  async function handleGenerer() {
    if (!accessToken || !projectId) return
    setIsGenerating(true)
    setGenerateError(null)
    try {
      const nouvelleAnalyse = await generateAipdAnalysis(accessToken, projectId)
      setAnalyses((current) => [nouvelleAnalyse, ...current])
    } catch (err) {
      // 502 attendu si Groq échoue après ses retries (voir RegulatoryAgentError
      // -> aipd_router._handle_aipd_error), même principe que RgpdDiagnosticPage.
      setGenerateError(
        err instanceof ApiError
          ? "La génération de l'analyse d'impact a échoué, réessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setIsGenerating(false)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Analyse d'impact (AIPD)</h1>
        <p className="text-sm text-gray-500">
          Génère une analyse d'impact guidée à partir des réponses de ton diagnostic RGPD. Chaque génération crée une
          nouvelle version — l'historique reste consultable ci-dessous.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={handleGenerer}
          disabled={isGenerating}
          className="self-start rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700 disabled:opacity-50"
        >
          {isGenerating ? "Génération en cours..." : "Générer une analyse d'impact"}
        </button>
        {generateError && <p className="text-sm text-red-600">{generateError}</p>}
      </div>

      {analyses.length === 0 ? (
        <p className="text-sm text-gray-500">Aucune analyse générée pour l'instant.</p>
      ) : (
        <ul className="flex flex-col gap-4">
          {analyses.map((analyse) => (
            <li key={analyse.id} className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4">
              <span className="text-xs text-gray-400">
                Générée le {new Date(analyse.generated_at).toLocaleDateString("fr-FR")}
              </span>
              <p className="whitespace-pre-line text-sm text-gray-800">{analyse.contenu}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
