import { useState } from "react"
import type { RoadmapItemRead } from "../../api/roadmapApi"
import { GROUPE_LABELS } from "./groupeLabels"
import RoadmapGraphCanvas from "./RoadmapGraphCanvas"
import type { GridViewMode } from "./roadmapLayout"

interface GroupeNodesProps {
  groupe: string
  items: RoadmapItemRead[]
  viewMode: GridViewMode
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
  defaultOpen?: boolean
}

/**
 * Une phase de la roadmap : carte repliable (bouton flèche) qui révèle, une
 * fois ouverte, le graphe de dépendance de ses nœuds (RoadmapGraphCanvas).
 * Avant cette implémentation, ce composant rendait une simple liste de
 * StepNode ; il gère désormais la disposition en graphe/sentier au lieu d'une
 * liste verticale — voir roadmapLayout pour le calcul de position.
 */
export default function GroupeNodes({
  groupe,
  items,
  viewMode,
  selectedNodeId,
  onSelectNode,
  defaultOpen = false,
}: GroupeNodesProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const doneCount = items.filter((item) => item.statut === "termine" || item.statut === "non_necessaire").length

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="text-sm font-semibold text-gray-900">{GROUPE_LABELS[groupe] ?? groupe}</span>
        <span className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {doneCount}/{items.length}
          </span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
          </svg>
        </span>
      </button>

      {isOpen && (
        <div className="border-t border-gray-100 px-4 pb-4">
          <RoadmapGraphCanvas
            items={items}
            viewMode={viewMode}
            selectedNodeId={selectedNodeId}
            onSelectNode={onSelectNode}
          />
        </div>
      )}
    </div>
  )
}
