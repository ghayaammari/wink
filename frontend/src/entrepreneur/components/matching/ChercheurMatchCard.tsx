import { useState } from "react"
import type { ChercheurMatch } from "../../api/researchNeedApi"

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

interface ChercheurMatchCardProps {
  match: ChercheurMatch
  /** Contexte du besoin, affiché seulement dans la page transversale
   * "Recommandations intéressantes" (plusieurs besoins mélangés) -- absent
   * sur ResearchNeedsPage où le besoin est déjà le titre de la section. */
  needTitre?: string
  onToggleInteret: (match: ChercheurMatch) => void
  interetEnCours?: boolean
}

/**
 * Card de recommandation façon feed social (demande du 22/09/2026) : rang +
 * nom + niveau + étoile toujours visibles, description/explication
 * masquées jusqu'au clic sur la card -- une seule offre à la fois occupe
 * l'attention plutôt qu'un mur de texte pour chaque chercheur du feed.
 * Partagé entre ResearchNeedsPage.tsx (feed par besoin) et
 * RecommandationsInteressantesPage.tsx (feed transversal) pour ne pas
 * dupliquer ce rendu.
 */
export default function ChercheurMatchCard({
  match,
  needTitre,
  onToggleInteret,
  interetEnCours = false,
}: ChercheurMatchCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <li
      className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300"
    >
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
          {needTitre && <span className="text-[11px] text-gray-400">{needTitre}</span>}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-gray-900">
              #{match.rang} — {match.nom}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${NIVEAU_STYLES[match.niveau_pertinence]}`}>
              {NIVEAU_LABELS[match.niveau_pertinence]}
            </span>
          </div>
          {!expanded && <span className="text-xs text-gray-400">Toucher pour voir l'explication</span>}
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onToggleInteret(match)
          }}
          disabled={interetEnCours}
          title={match.interesse ? "Retirer de mes recommandations intéressantes" : "Marquer comme intéressé"}
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
        <p className="border-t border-gray-100 pt-2 text-xs text-gray-600">{match.explication}</p>
      )}
    </li>
  )
}
