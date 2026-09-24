import { useEffect, useState } from "react"
import StartupMatchCard from "../components/matching/StartupMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  listStartupsInteressantes,
  toggleStartupInteret,
  type StartupInteressante,
  type StartupMatch,
} from "../api/investmentOfferApi"

type LoadState = "loading" | "ready" | "error"

/**
 * "Startups intéressantes" — sous-section du sidebar sous "Mes offres" :
 * vue transversale de toutes les recommandations de startups marquées
 * "intéressé" par l'investisseur, à travers toutes ses offres déposées
 * (InvestmentOfferDetailPage reste la vue par offre). Retirer une étoile
 * ici la fait disparaître de la liste immédiatement (elle reste juste "non
 * intéressé" côté offre d'origine). Miroir exact de
 * RecommandationsInteressantesPage.tsx côté entrepreneur.
 */
export default function InterestingStartupsPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [recommandations, setRecommandations] = useState<StartupInteressante[]>([])
  const [error, setError] = useState<string | null>(null)
  const [interetEnCoursId, setInteretEnCoursId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      setRecommandations(await listStartupsInteressantes(accessToken))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger tes startups intéressantes.")
      setState("error")
    })
  }, [accessToken])

  async function handleToggleInteret(offerId: string, m: StartupMatch) {
    if (!accessToken) return
    setInteretEnCoursId(m.project_id)
    try {
      await toggleStartupInteret(accessToken, offerId, m.project_id, !m.interesse)
      // Toujours un retrait ici (cette page ne montre que des "intéressé"=true) --
      // pas besoin de relire le serveur, on enlève juste la carte de la liste.
      setRecommandations((current) =>
        current.filter((r) => !(r.offer_id === offerId && r.match.project_id === m.project_id)),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Startups intéressantes</h1>
        <p className="text-sm text-gray-500">
          Les startups que tu as marquées comme intéressantes, toutes offres confondues.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {recommandations.length === 0 ? (
        <p className="text-sm text-gray-500">
          Aucune startup marquée pour l'instant — clique sur l'étoile d'une recommandation depuis "Mes offres" pour la
          retrouver ici.
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {recommandations.map((r) => (
            <StartupMatchCard
              key={`${r.offer_id}-${r.match.project_id}`}
              match={r.match}
              offreTitre={r.offer_titre}
              onToggleInteret={(m) => handleToggleInteret(r.offer_id, m)}
              interetEnCours={interetEnCoursId === r.match.project_id}
            />
          ))}
        </ul>
      )}
    </div>
  )
}
