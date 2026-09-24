import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import { createInvestmentOffer, listInvestmentOffers, type InvestmentOfferRead } from "../api/investmentOfferApi"

type LoadState = "loading" | "ready" | "error"

const STADES_DISPONIBLES = [
  { value: "ideation", label: "Idéation" },
  { value: "pre_seed", label: "Pré-amorçage" },
  { value: "seed", label: "Amorçage" },
  { value: "serie_a", label: "Série A" },
]

/**
 * Page "Mes offres" côté investisseur (EPIC-07, volet Investisseur ->
 * Startup du matching) — dépôt d'une offre d'investissement, liste des
 * offres déjà déposées en cards. Contrairement à ResearchNeedsPage (feed de
 * matching affiché en accordéon sur la même page), chaque card ouvre ici
 * une page détail dédiée (InvestmentOfferDetailPage) : le matching et ses
 * recommandations vivent sur cette page détail, pas sur la liste.
 */
export default function InvestmentOffersPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [offers, setOffers] = useState<InvestmentOfferRead[]>([])
  const [error, setError] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [titre, setTitre] = useState("")
  const [description, setDescription] = useState("")
  const [montant, setMontant] = useState("")
  const [secteursCibles, setSecteursCibles] = useState("")
  const [stadesCibles, setStadesCibles] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      setOffers(await listInvestmentOffers(accessToken))
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger tes offres.")
      setState("error")
    })
  }, [accessToken])

  function toggleStade(value: string) {
    setStadesCibles((current) => (current.includes(value) ? current.filter((v) => v !== value) : [...current, value]))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const montantNombre = Number(montant)
    if (!accessToken || !titre.trim() || !description.trim() || !montantNombre || montantNombre <= 0) return
    setSubmitting(true)
    setError(null)
    try {
      const secteurs = secteursCibles
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
      const created = await createInvestmentOffer(
        accessToken,
        titre.trim(),
        description.trim(),
        montantNombre,
        secteurs,
        stadesCibles,
      )
      setOffers((current) => [created, ...current])
      setTitre("")
      setDescription("")
      setMontant("")
      setSecteursCibles("")
      setStadesCibles([])
      setShowForm(false)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Échec du dépôt de l'offre.")
    } finally {
      setSubmitting(false)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold text-gray-900">Mes offres</h1>
          <p className="text-sm text-gray-500">
            Dépose une offre d'investissement, puis lance le matching pour voir quelles startups de la plateforme
            correspondent à tes critères.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="shrink-0 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white"
        >
          {showForm ? "Annuler" : "Déposer une offre"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {showForm && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 rounded-lg border border-gray-200 p-4">
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

          <div className="flex flex-col gap-1">
            <label htmlFor="montant" className="text-sm font-medium text-gray-900">
              Montant proposé (€)
            </label>
            <input
              id="montant"
              type="number"
              min={1}
              value={montant}
              onChange={(e) => setMontant(e.target.value)}
              required
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="secteurs" className="text-sm font-medium text-gray-900">
              Secteurs ciblés
            </label>
            <input
              id="secteurs"
              type="text"
              value={secteursCibles}
              onChange={(e) => setSecteursCibles(e.target.value)}
              placeholder="ex: fintech, healthtech (séparés par des virgules)"
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <span className="text-xs text-gray-400">Laisse vide pour ne cibler aucun secteur en particulier.</span>
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium text-gray-900">Stades ciblés</span>
            <div className="flex flex-wrap gap-4">
              {STADES_DISPONIBLES.map((s) => (
                <label key={s.value} className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={stadesCibles.includes(s.value)}
                    onChange={() => toggleStade(s.value)}
                  />
                  {s.label}
                </label>
              ))}
            </div>
            <span className="text-xs text-gray-400">Aucun stade coché = tous les stades acceptés.</span>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="self-start rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {submitting ? "Dépôt en cours..." : "Déposer"}
          </button>
        </form>
      )}

      {offers.length === 0 ? (
        <p className="text-sm text-gray-500">Aucune offre déposée pour l'instant.</p>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {offers.map((offer) => (
            <OfferCard key={offer.id} offer={offer} />
          ))}
        </ul>
      )}
    </div>
  )
}

function OfferCard({ offer }: { offer: InvestmentOfferRead }) {
  return (
    <li>
      <Link
        to={`/investisseur/offres/${offer.id}`}
        className="flex h-full flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300 hover:shadow"
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-semibold text-gray-900">{offer.titre}</span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
              offer.statut === "ouvert" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
            }`}
          >
            {offer.statut === "ouvert" ? "Ouverte" : "Fermée"}
          </span>
        </div>
        <p className="line-clamp-2 text-xs text-gray-500">{offer.description}</p>
        <span className="mt-auto text-sm font-medium text-gray-700">
          {offer.montant_propose.toLocaleString("fr-FR")} €
        </span>
      </Link>
    </li>
  )
}
