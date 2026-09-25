import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import StartupMatchCard from "../components/matching/StartupMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  getInvestmentOffer,
  getStartupMatching,
  runStartupMatching,
  toggleStartupInteret,
  updateInvestmentOfferStatut,
  type InvestmentOfferMatchRead,
  type InvestmentOfferRead,
  type StartupMatch,
} from "../api/investmentOfferApi"

type LoadState = "loading" | "ready" | "error"

const STADE_LABELS: Record<string, string> = {
  ideation: "Idéation",
  pre_seed: "Pré-amorçage",
  seed: "Amorçage",
  serie_a: "Série A",
}

/**
 * Page détail d'une offre d'investissement — affiche l'offre complète, et
 * le bouton "Visualiser" qui déclenche le matching_agent_investisseur
 * (agents/matching_agent/investisseur_matching_service.py) pour trouver les
 * startups pertinentes. Les recommandations apparaissent en dessous, en
 * feed (StartupMatchCard), avec l'étoile "intéressé" -- même principe que
 * ResearchNeedsPage côté entrepreneur, mais sur une page dédiée plutôt qu'en
 * accordéon dans la liste (demande produit du 24/09/2026).
 *
 * Le matching n'est jamais lancé automatiquement à l'ouverture de la page
 * (appel LLM+tools coûteux) : au montage, on relit juste le dernier
 * résultat persisté (GET, lecture DB gratuite) ; "Visualiser"/"Relancer le
 * matching" déclenche le calcul (POST) sur clic explicite.
 */
export default function InvestmentOfferDetailPage() {
  const { offerId } = useParams<{ offerId: string }>()
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [offer, setOffer] = useState<InvestmentOfferRead | null>(null)
  const [match, setMatch] = useState<InvestmentOfferMatchRead | null>(null)
  const [matchLoaded, setMatchLoaded] = useState(false)
  const [matching, setMatching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [interetEnCoursId, setInteretEnCoursId] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken || !offerId) return
      const [loadedOffer, loadedMatch] = await Promise.all([
        getInvestmentOffer(accessToken, offerId),
        getStartupMatching(accessToken, offerId).catch(() => null),
      ])
      setOffer(loadedOffer)
      setMatch(loadedMatch)
      setMatchLoaded(true)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger cette offre.")
      setState("error")
    })
  }, [accessToken, offerId])

  async function handleToggleStatut() {
    if (!accessToken || !offer) return
    const nextStatut = offer.statut === "ouvert" ? "ferme" : "ouvert"
    try {
      setOffer(await updateInvestmentOfferStatut(accessToken, offer.id, nextStatut))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour du statut.")
    }
  }

  async function handleVisualiser() {
    if (!accessToken || !offerId) return
    setMatching(true)
    setError(null)
    try {
      setMatch(await runStartupMatching(accessToken, offerId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec du matching.")
    } finally {
      setMatching(false)
    }
  }

  async function handleToggleInteret(m: StartupMatch) {
    if (!accessToken || !offerId) return
    setInteretEnCoursId(m.project_id)
    try {
      setMatch(await toggleStartupInteret(accessToken, offerId, m.project_id, !m.interesse))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error" || !offer) return <p className="text-sm text-red-600">{error}</p>

  return (
    <div className="flex flex-col gap-6">
      <Link to="/investisseur/offres" className="text-sm text-gray-500 hover:text-gray-700">
        ← Mes offres
      </Link>

      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h1 className="text-xl font-semibold text-gray-900">{offer.titre}</h1>
          <p className="text-sm text-gray-600">{offer.description}</p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <span className="rounded-full bg-gray-100 px-2 py-0.5 font-medium text-gray-700">
              {offer.montant_propose.toLocaleString("fr-FR")} €
            </span>
            {offer.secteurs_cibles.map((s) => (
              <span key={s} className="rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-700">
                {s}
              </span>
            ))}
            {offer.stades_cibles.map((s) => (
              <span key={s} className="rounded-full bg-purple-50 px-2 py-0.5 text-purple-700">
                {STADE_LABELS[s] ?? s}
              </span>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={handleToggleStatut}
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
            offer.statut === "ouvert" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
          }`}
        >
          {offer.statut === "ouvert" ? "Ouverte" : "Fermée"}
        </button>
      </div>

      <div className="flex flex-col gap-3 border-t border-gray-100 pt-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium text-gray-700">Startups recommandées</span>
          <button
            type="button"
            onClick={handleVisualiser}
            disabled={matching}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {matching ? "Matching en cours..." : match ? "Relancer le matching" : "Visualiser"}
          </button>
        </div>

        {error && <p className="text-xs text-red-600">{error}</p>}

        {!matchLoaded && !matching && <p className="text-xs text-gray-400">Chargement...</p>}

        {matchLoaded && !match && !matching && (
          <p className="text-xs text-gray-400">
            Aucun matching généré pour l'instant — clique sur "Visualiser" pour lancer la recherche.
          </p>
        )}

        {match && (
          <div className="flex flex-col gap-2">
            <p className="text-xs italic text-gray-500">{match.synthese}</p>
            {match.matches.length === 0 ? (
              <p className="text-xs text-gray-500">Aucune startup pertinente trouvée pour cette offre.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {match.matches
                  .slice()
                  .sort((a, b) => a.rang - b.rang)
                  .map((m) => (
                    <StartupMatchCard
                      key={m.project_id}
                      match={m}
                      onToggleInteret={handleToggleInteret}
                      interetEnCours={interetEnCoursId === m.project_id}
                    />
                  ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
