import { useEffect, useState } from "react"
import OfferMatchCard from "../components/matching/OfferMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import { listInterestingOffers, toggleOfferInteret, type OfferMatch } from "../api/offerMatchingApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * Sous-section "Offres intéressantes" du sidebar, sous "Investissement" --
 * les offres d'investissement que l'entrepreneur a marquées "intéressé"
 * depuis InvestmentOpportunitiesPage.tsx. Contrairement au côté chercheur
 * (RecommandationsInteressantesPage.tsx, qui agrège plusieurs besoins) ou
 * investisseur (InterestingStartupsPage.tsx, qui agrège plusieurs offres),
 * un projet n'a qu'UN SEUL feed d'offres -- listInterestingOffers filtre
 * simplement ce feed unique, pas d'agrégation cross-lignes nécessaire.
 */
export default function InterestingOffersPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [offres, setOffres] = useState<OfferMatch[]>([])
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
      setOffres(await listInterestingOffers(accessToken, project.id))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger tes offres intéressantes.")
      setState("error")
    })
  }, [accessToken])

  async function handleToggleInteret(m: OfferMatch) {
    if (!accessToken || !projectId) return
    setInteretEnCoursId(m.offer_id)
    try {
      await toggleOfferInteret(accessToken, projectId, m.offer_id, !m.interesse)
      // Toujours un retrait ici (cette page ne montre que des "intéressé"=true) --
      // pas besoin de relire le serveur, on enlève juste la carte de la liste.
      setOffres((current) => current.filter((o) => o.offer_id !== m.offer_id))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "no_project") return <p className="text-sm text-gray-500">Complète d'abord ton profil de projet.</p>
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Offres intéressantes</h1>
        <p className="text-sm text-gray-500">Les offres d'investissement que tu as marquées comme intéressantes.</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {offres.length === 0 ? (
        <p className="text-sm text-gray-500">
          Aucune offre marquée pour l'instant — clique sur l'étoile d'une recommandation depuis "Investissement" pour
          la retrouver ici.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {offres.map((m) => (
            <OfferMatchCard
              key={m.offer_id}
              match={m}
              onToggleInteret={handleToggleInteret}
              interetEnCours={interetEnCoursId === m.offer_id}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
