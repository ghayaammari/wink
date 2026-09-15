import type { RoadmapItemRead } from "../../api/roadmapApi"
import { NODE_HEIGHT, NODE_WIDTH } from "./roadmapLayout"

interface StepNodeProps {
  item: RoadmapItemRead
  x: number
  y: number
  isSelected: boolean
  onSelect: (nodeId: string) => void
}

const STATUT_STYLE: Record<string, { border: string; bg: string; dot: string }> = {
  verrouille: { border: "border-gray-200", bg: "bg-gray-50", dot: "bg-gray-300" },
  a_faire: { border: "border-amber-300", bg: "bg-amber-50", dot: "bg-amber-500" },
  en_cours: { border: "border-blue-300", bg: "bg-blue-50", dot: "bg-blue-500" },
  termine: { border: "border-green-300", bg: "bg-green-50", dot: "bg-green-500" },
  non_necessaire: { border: "border-gray-200", bg: "bg-gray-50", dot: "bg-gray-300" },
}

/**
 * Un nœud de la roadmap affiché comme "chip" cliquable dans le graphe —
 * positionné en absolu par le parent (RoadmapGraphCanvas, à partir de
 * `roadmapLayout.computeGroupLayout`). Le détail complet (description,
 * prérequis, actions) est dans le popup ouvert par `onSelect`, pas ici — voir
 * StepDetailPopup. Avant cette implémentation, ce composant portait aussi la
 * checkbox "fait" et l'upload de preuve inline : ce n'est plus le cas, ces
 * actions vivent désormais dans le popup.
 */
export default function StepNode({ item, x, y, isSelected, onSelect }: StepNodeProps) {
  const style = STATUT_STYLE[item.statut] ?? STATUT_STYLE.verrouille

  return (
    <button
      type="button"
      onClick={() => onSelect(item.node_id)}
      style={{ left: x, top: y, width: NODE_WIDTH, height: NODE_HEIGHT }}
      className={`absolute flex flex-col justify-center gap-1 rounded-lg border px-3 py-2 text-left transition ${style.border} ${style.bg} ${
        isSelected ? "ring-2 ring-indigo-500" : "hover:border-gray-400"
      }`}
    >
      <span className="flex items-center gap-2">
        <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
        <span className="truncate text-xs font-medium text-gray-900">{item.node_snapshot.nom}</span>
      </span>
    </button>
  )
}
