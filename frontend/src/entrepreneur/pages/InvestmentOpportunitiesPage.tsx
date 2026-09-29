import { useEffect, useState } from "react"
import OfferCatalogueCard from "../components/matching/OfferCatalogueCard"
import OfferMatchCard from "../components/matching/OfferMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import { listOfferCatalogue, type OfferCatalogueItem } from "../api/investmentOfferCatalogueApi"
import {
  getOfferMatching,
  runOfferMatching,
  toggleOfferInteret,
  type OfferMatch,
  type ProjectOfferMatchRead,
} from "../api/offerMatchingApi"

function ICON_TREND_HEADER({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <path d="M2.5 15 8 9.5l3 3 5.5-5.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.5 6.5h3.5V10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * Page "Investissement" côté entrepreneur (service 6.6.1, "Feed de matching
 * investisseurs") — deux étapes bien distinctes :
 *
 * 1. Consultation libre : TOUTES les offres ouvertes (catalogue brut, lu
 *    directement en base via investmentOfferCatalogueApi.ts, gratuit,
 *    chargé au montage) — l'entrepreneur doit pouvoir parcourir le marché
 *    sans dépendre de l'agent.
 * 2. Matching : bouton "Faire le matching" explicite, qui déclenche l'agent
 *    (agents/matching_agent/startup_offer_matching_service.py, coûteux,
 *    LLM+tools) et affiche son verdict scoré/expliqué séparément
 *    (offerMatchingApi.ts) -- jamais lancé automatiquement à l'arrivée sur
 *    la page.
 *
 * L'étoile "intéressé" ne s'applique qu'aux résultats du matching (section
 * 2) : marquer "intéressé" suppose une entrée dans project_offer_matches,
 * qui n'existe qu'une fois l'agent passé -- absente du catalogue brut.
 */
export default function InvestmentOpportunitiesPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [catalogue, setCatalogue] = useState<OfferCatalogueItem[]>([])
  const [matching, setMatching] = useState<ProjectOfferMatchRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lancementEnCours, setLancementEnCours] = useState(false)
  const [interetEnCoursId, setInteretEnCoursId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const [project, offres] = await Promise.all([getMyProject(accessToken), listOfferCatalogue(accessToken)])
      setCatalogue(offres)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      setMatching(await getOfferMatching(accessToken, project.id))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger les offres d'investissement.")
      setState("error")
    })
  }, [accessToken])

  async function handleLancerMatching() {
    if (!accessToken || !projectId) return
    setLancementEnCours(true)
    setError(null)
    try {
      setMatching(await runOfferMatching(accessToken, projectId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec du calcul du matching. Réessaie dans un instant.")
    } finally {
      setLancementEnCours(false)
    }
  }

  async function handleToggleInteret(m: OfferMatch) {
    if (!accessToken || !projectId) return
    setInteretEnCoursId(m.offer_id)
    try {
      setMatching(await toggleOfferInteret(accessToken, projectId, m.offer_id, !m.interesse))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>

  const matchesTries = [...(matching?.matches ?? [])].sort((a, b) => a.rang - b.rang)

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
          <ICON_TREND_HEADER />
        </div>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold text-gray-900">Investissement</h1>
          <p className="text-sm text-gray-500">Parcours les offres d'investissement disponibles, puis lance le matching pour ton projet.</p>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold text-gray-700">Toutes les offres disponibles</h2>
        {catalogue.length === 0 && <p className="text-sm text-gray-500">Aucune offre ouverte pour l'instant.</p>}
        {catalogue.length > 0 && (
          <ul className="flex flex-col gap-3">
            {catalogue.map((offer) => (
              <OfferCatalogueCard key={offer.id} offer={offer} />
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-3 border-t border-gray-100 pt-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-gray-700">Recommandées pour ton projet</h2>
          {state === "ready" && (
            <button
              type="button"
              onClick={handleLancerMatching}
              disabled={lancementEnCours}
              className="rounded-lg bg-wink-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-wink-700 disabled:opacity-50"
            >
              {lancementEnCours ? "Analyse en cours…" : matching ? "Relancer le matching" : "Faire le matching"}
            </button>
          )}
        </div>

        {state === "no_project" && <p className="text-sm text-gray-500">Complète d'abord ton profil de projet pour lancer le matching.</p>}

        {state === "ready" && matching && <p className="text-sm text-gray-500">{matching.synthese}</p>}

        {state === "ready" && matching === null && !lancementEnCours && (
          <p className="text-sm text-gray-500">Clique sur "Faire le matching" pour voir les offres recommandées pour ton projet.</p>
        )}

        {state === "ready" && matching && matchesTries.length === 0 && (
          <p className="text-sm text-gray-500">Aucune offre pertinente pour ton projet pour l'instant.</p>
        )}

        {matchesTries.length > 0 && (
          <ul className="flex flex-col gap-3">
            {matchesTries.map((m) => (
              <OfferMatchCard
                key={m.offer_id}
                match={m}
                onToggleInteret={handleToggleInteret}
                interetEnCours={interetEnCoursId === m.offer_id}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
