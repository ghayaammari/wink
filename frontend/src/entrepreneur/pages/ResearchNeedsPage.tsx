import { useEffect, useState } from "react"
import ChercheurMatchCard from "../components/matching/ChercheurMatchCard"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  createResearchNeed,
  getChercheurMatching,
  listResearchNeeds,
  runChercheurMatching,
  toggleChercheurInteret,
  updateResearchNeedStatut,
  type ChercheurMatch,
  type ResearchNeedMatchRead,
  type ResearchNeedRead,
  type TypeBesoin,
} from "../api/researchNeedApi"

function ICON_SEARCH_HEADER({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className={className}>
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="m17 17-4-4" strokeLinecap="round" />
    </svg>
  )
}

type LoadState = "loading" | "ready" | "no_project" | "error"

/**
 * Page "Besoins scientifiques" côté entrepreneur (renommee le 27/09/2026,
 * etait "Recherche" -- confondu avec une fonction de recherche/moteur).
 * Service 7.7.1 : dépôt d'un besoin
 * scientifique (problème à résoudre ou expertise recherchée), liste des
 * besoins déjà déposés, et déclenchement du matching_agent (service 7.7.2,
 * agents/matching_agent/chercheur_matching_service.py) par besoin.
 *
 * Le matching n'est jamais lancé automatiquement au dépôt d'un besoin
 * (appel LLM+tools coûteux, même raisonnement que les sous-agents
 * compliance_agent) : chaque NeedCard relit juste le dernier résultat
 * persisté au montage (GET, lecture DB gratuite), et ne relance l'agent
 * (POST) que sur clic explicite "Lancer le matching".
 *
 * Affichage en feed (demande du 22/09/2026) : chaque recommandation est une
 * card ChercheurMatchCard cliquable (nom/rang/niveau visibles, explication
 * masquée jusqu'au clic), avec une étoile pour la marquer "intéressé" — ce
 * qui la fait apparaître dans la sous-partie "Recommandations
 * intéressantes" du sidebar (voir RecommandationsInteressantesPage.tsx).
 */
export default function ResearchNeedsPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [needs, setNeeds] = useState<ResearchNeedRead[]>([])
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [typeBesoin, setTypeBesoin] = useState<TypeBesoin>("probleme")
  const [titre, setTitre] = useState("")
  const [description, setDescription] = useState("")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      setNeeds(await listResearchNeeds(accessToken, project.id))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger tes besoins de recherche.")
      setState("error")
    })
  }, [accessToken])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!accessToken || !projectId || !titre.trim() || !description.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const created = await createResearchNeed(accessToken, projectId, typeBesoin, titre.trim(), description.trim())
      setNeeds((current) => [created, ...current])
      setTitre("")
      setDescription("")
      setTypeBesoin("probleme")
      setShowForm(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec du dépôt du besoin.")
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggleStatut(need: ResearchNeedRead) {
    if (!accessToken || !projectId) return
    const nextStatut = need.statut === "ouvert" ? "ferme" : "ouvert"
    try {
      const updated = await updateResearchNeedStatut(accessToken, projectId, need.id, nextStatut)
      setNeeds((current) => current.map((n) => (n.id === updated.id ? updated : n)))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec de la mise à jour du statut.")
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-gray-900">Besoins scientifiques</h1>
        <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
            <ICON_SEARCH_HEADER />
          </div>
          <div className="flex flex-col gap-0.5">
            <h1 className="text-xl font-semibold text-gray-900">Besoins scientifiques</h1>
            <p className="text-sm text-gray-500">
              Dépose un problème que ta startup doit résoudre, ou une expertise dont elle a besoin — puis lance le
              matching pour voir quels chercheurs de la plateforme sont pertinents.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="shrink-0 rounded-lg bg-wink-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-wink-700"
        >
          {showForm ? "Annuler" : "Déposer un besoin"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border border-gray-200 p-4">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-900">Type de besoin</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  checked={typeBesoin === "probleme"}
                  onChange={() => setTypeBesoin("probleme")}
                />
                Un problème concret à résoudre
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="radio"
                  checked={typeBesoin === "expertise"}
                  onChange={() => setTypeBesoin("expertise")}
                />
                Une expertise recherchée
              </label>
            </div>
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="titre" className="text-sm font-medium text-gray-900">
              Titre
            </label>
            <input
              id="titre"
              type="text"
              value={titre}
              onChange={(e) => setTitre(e.target.value)}
              maxLength={255}
              required
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="description" className="text-sm font-medium text-gray-900">
              Description
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              rows={4}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="self-start rounded-lg bg-wink-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-wink-700 disabled:opacity-50"
          >
            {submitting ? "Dépôt en cours..." : "Déposer"}
          </button>
        </form>
      )}

      {needs.length === 0 ? (
        <p className="text-sm text-gray-500">Aucun besoin déposé pour l'instant.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {needs.map((need) => (
            <NeedCard
              key={need.id}
              need={need}
              projectId={projectId as string}
              accessToken={accessToken as string}
              onToggleStatut={handleToggleStatut}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

interface NeedCardProps {
  need: ResearchNeedRead
  projectId: string
  accessToken: string
  onToggleStatut: (need: ResearchNeedRead) => void
}

function NeedCard({ need, projectId, accessToken, onToggleStatut }: NeedCardProps) {
  const [match, setMatch] = useState<ResearchNeedMatchRead | null>(null)
  const [matchLoaded, setMatchLoaded] = useState(false)
  const [matching, setMatching] = useState(false)
  const [matchError, setMatchError] = useState<string | null>(null)
  const [interetEnCoursId, setInteretEnCoursId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getChercheurMatching(accessToken, projectId, need.id)
      .then((result) => {
        if (!cancelled) setMatch(result)
      })
      .catch(() => {
        // Lecture silencieuse : pas grave si le résultat existant ne charge pas,
        // le bouton "Lancer le matching" reste disponible pour réessayer.
      })
      .finally(() => {
        if (!cancelled) setMatchLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, projectId, need.id])

  async function handleLancerMatching() {
    setMatching(true)
    setMatchError(null)
    try {
      const result = await runChercheurMatching(accessToken, projectId, need.id)
      setMatch(result)
    } catch (err) {
      setMatchError(err instanceof ApiError ? err.message : "Échec du matching.")
    } finally {
      setMatching(false)
    }
  }

  async function handleToggleInteret(m: ChercheurMatch) {
    setInteretEnCoursId(m.researcher_profile_id)
    try {
      const updated = await toggleChercheurInteret(
        accessToken,
        projectId,
        need.id,
        m.researcher_profile_id,
        !m.interesse,
      )
      setMatch(updated)
    } catch (err) {
      setMatchError(err instanceof ApiError ? err.message : "Échec de la mise à jour de l'intérêt.")
    } finally {
      setInteretEnCoursId(null)
    }
  }

  return (
    <li className="flex flex-col gap-3 rounded-lg border border-gray-200 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900">{need.titre}</span>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {need.type_besoin === "probleme" ? "Problème" : "Expertise"}
            </span>
          </div>
          <span className="text-xs text-gray-500">{need.description}</span>
        </div>
        <button
          type="button"
          onClick={() => onToggleStatut(need)}
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
            need.statut === "ouvert" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
          }`}
        >
          {need.statut === "ouvert" ? "Ouvert" : "Fermé"}
        </button>
      </div>

      <div className="flex flex-col gap-2 border-t border-gray-100 pt-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-gray-700">Matching chercheurs</span>
          <button
            type="button"
            onClick={handleLancerMatching}
            disabled={matching}
            className="rounded-lg bg-wink-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {matching ? "Matching en cours..." : match ? "Relancer le matching" : "Lancer le matching"}
          </button>
        </div>

        {matchError && <p className="text-xs text-red-600">{matchError}</p>}

        {!matchLoaded && !matching && <p className="text-xs text-gray-400">Chargement...</p>}

        {matchLoaded && !match && !matching && (
          <p className="text-xs text-gray-400">Aucun matching généré pour l'instant.</p>
        )}

        {match && (
          <div className="flex flex-col gap-2">
            <p className="text-xs italic text-gray-500">{match.synthese}</p>
            {match.matches.length === 0 ? (
              <p className="text-xs text-gray-500">Aucun chercheur pertinent trouvé pour ce besoin.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {match.matches
                  .slice()
                  .sort((a, b) => a.rang - b.rang)
                  .map((m) => (
                    <ChercheurMatchCard
                      key={m.researcher_profile_id}
                      match={m}
                      onToggleInteret={handleToggleInteret}
                      interetEnCours={interetEnCoursId === m.researcher_profile_id}
                    />
                  ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </li>
  )
}
