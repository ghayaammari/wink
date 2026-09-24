import { useState } from "react"
import type { StartupMatch } from "../../api/investmentOfferApi"

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

interface StartupMatchCardProps {
  match: StartupMatch
  /** Contexte de l'offre, affiché seulement dans la page transversale
   * "Startups intéressantes" (plusieurs offres mélangées) -- absent sur la
   * page détail d'une offre où l'offre est déjà le titre de la section.
   * Même convention que ChercheurMatchCard.tsx::needTitre. */
  offreTitre?: string
  onToggleInteret: (match: StartupMatch) => void
  interetEnCours?: boolean
}

/**
 * Card de recommandation façon feed social — même composant/logique que
 * ChercheurMatchCard.tsx (côté entrepreneur), en miroir pour le sens
 * Investisseur -> Startup : rang + nom + niveau + étoile toujours visibles.
 * Une fois dépliée, la card montre 2 choses distinctes : l'explication de
 * l'agent (pourquoi ce match), ET la fiche vivante de la startup elle-même
 * (secteur, stade, localisation, description, technologies, lien du site) --
 * demande explicite du 24/09/2026 ("les startups doivent se montrer") :
 * l'investisseur doit voir la startup, pas seulement une phrase générée.
 * Partagé entre InvestmentOfferDetailPage (feed par offre) et
 * InterestingStartupsPage (feed transversal).
 */
export default function StartupMatchCard({
  match,
  offreTitre,
  onToggleInteret,
  interetEnCours = false,
}: StartupMatchCardProps) {
  const [expanded, setExpanded] = useState(false)

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
        <div className="flex flex-1 items-start gap-3">
          {match.logo_url && (
            <img
              src={match.logo_url}
              alt=""
              className="mt-0.5 h-9 w-9 shrink-0 rounded-lg border border-gray-100 object-cover"
            />
          )}
          <div className="flex flex-col gap-1">
            {offreTitre && <span className="text-[11px] text-gray-400">{offreTitre}</span>}
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-gray-900">
                #{match.rang} — {match.nom}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${NIVEAU_STYLES[match.niveau_pertinence]}`}>
                {NIVEAU_LABELS[match.niveau_pertinence]}
              </span>
              {match.stade && (
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600">
                  {STADE_LABELS[match.stade] ?? match.stade}
                </span>
              )}
            </div>
            {(match.secteur || match.localisation) && (
              <span className="text-xs text-gray-500">
                {[match.secteur, match.localisation].filter(Boolean).join(" · ")}
              </span>
            )}
            {!expanded && <span className="text-xs text-gray-400">Toucher pour voir la fiche de la startup</span>}
          </div>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onToggleInteret(match)
          }}
          disabled={interetEnCours}
          title={match.interesse ? "Retirer des startups intéressantes" : "Marquer comme intéressée"}
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

          {(match.value_proposition || (match.technologies && match.technologies.length > 0) || match.website_url) && (
            <div className="flex flex-col gap-2 rounded-lg bg-gray-50 p-3">
              <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400">La startup</p>
              {match.value_proposition && <p className="text-xs text-gray-700">{match.value_proposition}</p>}
              {match.technologies && match.technologies.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {match.technologies.map((tech) => (
                    <span key={tech} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-gray-600 ring-1 ring-gray-200">
                      {tech}
                    </span>
                  ))}
                </div>
              )}
              {match.website_url && (
                <a
                  href={match.website_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs font-medium text-indigo-600 hover:underline"
                >
                  Voir le site de la startup ↗
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  )
}
