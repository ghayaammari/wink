import type { RoadmapItemRead } from "../../api/roadmapApi"
import { GROUPE_LABELS } from "./groupeLabels"
import PathStepCard from "./PathStepCard"
import { computeFullPathLayout } from "./roadmapLayout"

interface RoadmapPathViewProps {
  items: RoadmapItemRead[]
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
}

/**
 * Vue "Parcours" : toute la roadmap comme un seul chemin vertical continu,
 * sections séparées par une étiquette de groupe — à la différence des vues
 * Graphe/Sentier qui restent des cartes de phase repliables (voir
 * GroupeNodes). Même popup de détail que les deux autres vues
 * (StepDetailPopup, ouvert par PlanActionPage) : aucune duplication de la
 * logique d'action (marquer fait, déposer une preuve).
 */
export default function RoadmapPathView({ items, selectedNodeId, onSelectNode }: RoadmapPathViewProps) {
  const layout = computeFullPathLayout(items)
  const byId = new Map(items.map((item) => [item.node_id, item]))
  const doneCount = items.filter((item) => item.statut === "termine" || item.statut === "non_necessaire").length
  const progressPct = items.length > 0 ? Math.round((doneCount / items.length) * 100) : 0

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-4 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
          <div className="h-full rounded-full bg-indigo-600 transition-[width]" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="whitespace-nowrap text-xs font-medium text-gray-600">
          {doneCount}/{items.length}
        </span>
      </div>

      <div className="relative overflow-x-auto" style={{ minHeight: layout.height }}>
        <div className="relative" style={{ width: layout.width, height: layout.height }}>
          <svg className="pointer-events-none absolute left-0 top-0" width={layout.width} height={layout.height}>
            {layout.edges.map((edge) => (
              <path
                key={`${edge.from}->${edge.to}`}
                d={edge.path}
                fill="none"
                stroke={edge.done ? "#4f46e5" : "#d1d5db"}
                strokeWidth={edge.done ? 2 : 1.5}
                strokeDasharray={edge.done ? undefined : "4 4"}
              />
            ))}
          </svg>

          {layout.headers.map((header) => (
            <div key={`${header.groupe}-${header.y}`} className="absolute left-0 w-full text-center" style={{ top: header.y }}>
              <span className="inline-block rounded-full border border-gray-100 bg-gray-50 px-3.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                {GROUPE_LABELS[header.groupe] ?? header.groupe}
              </span>
            </div>
          ))}

          {layout.positions.map((pos) => {
            const item = byId.get(pos.nodeId)
            if (!item) return null
            return (
              <PathStepCard
                key={pos.nodeId}
                item={item}
                x={pos.x}
                y={pos.y}
                width={pos.width}
                isSelected={selectedNodeId === pos.nodeId}
                onSelect={onSelectNode}
              />
            )
          })}
        </div>
      </div>
    </div>
  )
}
