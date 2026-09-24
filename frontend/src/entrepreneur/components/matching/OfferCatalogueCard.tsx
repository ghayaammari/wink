import { useState } from "react"
import type { OfferCatalogueItem } from "../../api/investmentOfferCatalogueApi"

const STADE_LABELS: Record<string, string> = {
  ideation: "Idéation",
  pre_seed: "Pre-seed",
  seed: "Seed",
  serie_a: "Série A",
}

interface OfferCatalogueCardProps {
  offer: OfferCatalogueItem
}

/**
 * Card d'une offre du catalogue brut (voir OfferMatchCard.tsx pour la
 * version scorée) — ni rang, ni niveau de pertinence, ni étoile "intéressé"
 * : l'agent ne s'est pas encore prononcé sur cette offre, ce n'est qu'une
 * consultation libre. L'étoile n'apparaît qu'après matching (OfferMatchCard),
 * puisque marquer "intéressé" suppose une entrée dans project_offer_matches.
 */
export default function OfferCatalogueCard({ offer }: OfferCatalogueCardProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <li
      role="button"
      tabIndex={0}
      onClick={() => setExpanded((v) => !v)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") setExpanded((v) => !v)
      }}
      className="flex cursor-pointer flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-gray-900">{offer.titre}</span>
      </div>
      <span className="text-xs text-gray-500">
        {[`${offer.montant_propose.toLocaleString("fr-FR")} €`, offer.investor_type].filter(Boolean).join(" · ")}
      </span>

      {!expanded && <span className="text-xs text-gray-400">Toucher pour voir le détail de l'offre</span>}

      {expanded && (
        <div className="flex flex-col gap-3 border-t border-gray-100 pt-2">
          <p className="text-xs text-gray-600">{offer.description}</p>
          {(offer.secteurs_cibles.length > 0 || offer.stades_cibles.length > 0) && (
            <div className="flex flex-col gap-2 rounded-lg bg-gray-50 p-3">
              {offer.secteurs_cibles.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {offer.secteurs_cibles.map((secteur) => (
                    <span key={secteur} className="rounded-full bg-white px-2 py-0.5 text-[11px] text-gray-600 ring-1 ring-gray-200">
                      {secteur}
                    </span>
                  ))}
                </div>
              )}
              {offer.stades_cibles.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {offer.stades_cibles.map((stade) => (
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
