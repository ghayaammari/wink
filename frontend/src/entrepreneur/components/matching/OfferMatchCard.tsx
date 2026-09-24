import { useState } from "react"
import type { OfferMatch } from "../../api/offerMatchingApi"

const NIVEAU_LABELS: Record<string, string> = {
  fort: "Match fort",
  moyen: "Match moyen",
  faible: "Match faible",
}

const NIVEAU_STYLES: Record<string, string> = {
  fort: "bg-green-50 text-green-700",
  moyen: "bg-amber-50 text-amber-700",
  faible: "bg-gray-100 text-gray-600",
}

const STADE_LABELS: Record<string, string> = {
  ideation: "Idéation",
  pre_seed: "Pre-seed",
  seed: "Seed",
  serie_a: "Série A",
}

const ICON_STAR_FILLED = (
  <path d="M12 2.25 14.9 8.6l7 .61-5.29 4.6 1.6 6.87L12 17.06l-6.21 3.62 1.6-6.87-5.29-4.6 7-.61L12 2.25Z" />
)

const ICON_STAR_OUTLINE = (
  <path
    strokeLinecap="round"
    strokeLinejoin="round"
    d="M11.48 3.5c.14-.3.55-.3.69 0l2.09 4.61a.5.5 0 0 0 .39.28l5.05.55c.34.04.48.46.22.68l-3.79 3.36a.5.5 0 0 0-.16.49l1.12 4.94c.08.34-.29.6-.58.42l-4.32-2.65a.5.5 0 0 0-.52 0l-4.32 2.65c-.3.18-.66-.08-.58-.42l1.12-4.94a.5.5 0 0 0-.16-.49L4.04 9.62c-.26-.22-.12-.64.22-.68l5.05-.55a.5.5 0 0 0 .39-.28l2.09-4.6Z"
  />
)

interface OfferMatchCardProps {
  match: OfferMatch
  onToggleInteret: (match: OfferMatch) => void
  interetEnCours?: boolean
}

/**
 * Card de recommandation façon feed social — même composant/logique que
 * StartupMatchCard.tsx (côté investisseur), en miroir pour le sens
 * Startup -> Offres : rang + titre + niveau + étoile toujours visibles.
 * Une fois dépliée, montre l'explication de l'agent ET la fiche vivante de
 * l'offre (montant, secteurs/stades ciblés, type d'investisseur) -- même
 * raisonnement que StartupMatchCard ("les startups doivent se montrer"),
 * ici appliqué à l'offre. Une offre fermée entre-temps par l'investisseur
 * (statut) reste visible mais clairement annotée, jamais masquée en
 * silence -- l'entrepreneur doit comprendre pourquoi il ne peut plus agir
 * dessus. Partagé entre InvestmentOpportunitiesPage (feed du projet) et
 * InterestingOffersPage (offres marquées "intéressantes").
 */
export default function OfferMatchCard({ match, onToggleInteret, interetEnCours = false }: OfferMatchCardProps) {
  const [expanded, setExpanded] = useState(false)
  const fermee = match.statut === "ferme"

  return (
    <li className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") setExpanded((v) => !v)
        }}
        className="flex w-full cursor-pointer items-start justify-between gap-3 text-left"
      >
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-gray-900">
              #{match.rang} — {match.titre ?? "Offre supprimée"}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${NIVEAU_STYLES[match.niveau_pertinence]}`}>
              {NIVEAU_LABELS[match.niveau_pertinence]}
            </span>
            {fermee && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
                Offre fermée
              </span>
            )}
          </div>
          {(match.montant_propose || match.investor_type) && (
            <span className="text-xs text-gray-500">
              {[
                match.montant_propose ? `${match.montant_propose.toLocaleString("fr-FR")} €` : null,
                match.investor_type,
              ]
                .filter(Boolean)
                .join(" · ")}
            </span>
          )}
          {!expanded && <span className="text-xs text-gray-400">Toucher pour voir le détail de l'offre</span>}
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onToggleInteret(match)
          }}
          disabled={interetEnCours}
          title={match.interesse ? "Retirer des offres intéressantes" : "Marquer comme intéressante"}
          className={`shrink-0 rounded-full p-1.5 transition disabled:opacity-50 ${
            match.interesse ? "text-amber-500 hover:text-amber-600" : "text-gray-300 hover:text-amber-400"
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" strokeWidth={1.2} className="h-5 w-5">
            {match.interesse ? ICON_STAR_FILLED : ICON_STAR_OUTLINE}
          </svg>
        </button>
      </div>

      {expanded && (
        <div className="flex flex-col gap-3 border-t border-gray-100 pt-2">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">Pourquoi ce match</p>
            <p className="text-xs text-gray-600">{match.explication}</p>
          </div>

          {(match.secteurs_cibles?.length || match.stades_cibles?.length) && (
            <div className="flex flex-col gap-2 rounded-lg bg-gray-50 p-3">
              <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">L'offre</p>
              {match.secteurs_cibles && match.secteurs_cibles.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {match.secteurs_cibles.map((secteur) => (
                    <span key={secteur} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-gray-600 ring-1 ring-gray-200">
                      {secteur}
                    </span>
                  ))}
                </div>
              )}
              {match.stades_cibles && match.stades_cibles.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {match.stades_cibles.map((stade) => (
                    <span key={stade} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-gray-600 ring-1 ring-gray-200">
                      {STADE_LABELS[stade] ?? stade}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  )
}
