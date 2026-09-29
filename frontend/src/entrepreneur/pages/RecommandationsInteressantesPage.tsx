import { useEffect, useState } from "react"
import ChercheurMatchCard from "../components/matching/ChercheurMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  listRecommandationsInteressantes,
  toggleChercheurInteret,
  type ChercheurMatch,
  type RecommandationInteressante,
} from "../api/researchNeedApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * "Recommandations intéressantes" — sous-section du sidebar sous
 * "Besoins scientifiques" (demande du 22/09/2026, entrée renommee le
 * 27/09/2026 -- etait "Recherche") : vue transversale de toutes les
 * recommandations de chercheurs marquées "intéressé" par l'entrepreneur, à
 * travers tous ses besoins déposés (ResearchNeedsPage reste la vue par
 * besoin). Retirer une étoile ici la fait disparaître de la liste
 * immédiatement (elle reste juste "non intéressé" côté besoin d'origine).
 *
 * Pas de messagerie ici pour l'instant — mentionnée comme piste future par
 * l'entrepreneur mais aucun écran/backend n'est spécifié pour ça dans
 * l'architecture actuelle (Wink_architecture_fichiers.md), donc hors
 * périmètre de ce service tant que ce n'est pas cadré.
 */
export default function RecommandationsInteressantesPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [recommandations, setRecommandations] = useState<RecommandationInteressante[]>([])
  const [error, setError] = useState<string | null>(null)
  const [interetEnCoursId, setInteretEnCoursId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      setRecommandations(await listRecommandationsInteressantes(accessToken, project.id))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger tes recommandations intéressantes.")
      setState("error")
    })
  }, [accessToken])

  async function handleToggleInteret(needId: string, m: ChercheurMatch) {
    if (!accessToken || !projectId) return
    setInteretEnCoursId(m.researcher_profile_id)
    try {
      await toggleChercheurInteret(accessToken, projectId, needId, m.researcher_profile_id, !m.interesse)
      // Toujours un retrait ici (cette page ne montre que des "intéressé"=true) —
      // pas besoin de relire le serveur, on enlève juste la carte de la liste.
      setRecommandations((current) =>
        current.filter((r) => !(r.need_id === needId && r.match.researcher_profile_id === m.researcher_profile_id)),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-gray-900">Recommandations intéressantes</h1>
        <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Recommandations intéressantes</h1>
        <p className="text-sm text-gray-500">
          Les chercheurs que tu as marqués comme intéressants, tous besoins confondus.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {recommandations.length === 0 ? (
        <p className="text-sm text-gray-500">
          Aucune recommandation marquée pour l'instant — clique sur l'étoile d'une recommandation depuis "Besoins
          scientifiques" pour la retrouver ici.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {recommandations.map((r) => (
            <ChercheurMatchCard
              key={`${r.need_id}-${r.match.researcher_profile_id}`}
              match={r.match}
              needTitre={r.need_titre}
              onToggleInteret={(m) => handleToggleInteret(r.need_id, m)}
              interetEnCours={interetEnCoursId === r.match.researcher_profile_id}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
