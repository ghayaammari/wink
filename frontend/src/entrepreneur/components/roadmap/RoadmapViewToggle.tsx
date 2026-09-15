import type { RoadmapViewMode } from "./roadmapLayout"

interface RoadmapViewToggleProps {
  value: RoadmapViewMode
  onChange: (mode: RoadmapViewMode) => void
}

const OPTIONS: { mode: RoadmapViewMode; label: string }[] = [
  { mode: "graphe", label: "Graphe" },
  { mode: "sentier", label: "Sentier vertical" },
  { mode: "parcours", label: "Parcours" },
]

/** Bascule entre les trois styles d'affichage de la roadmap — les deux
 * premiers en grille par carte de phase repliable (voir GroupeNodes), le
 * troisième ("Parcours") en chemin vertical continu sans accordéon (voir
 * RoadmapPathView). Gardés tous les trois plutôt que de trancher pour
 * l'utilisateur. */
export default function RoadmapViewToggle({ value, onChange }: RoadmapViewToggleProps) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
      {OPTIONS.map(({ mode, label }) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
            value === mode ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
