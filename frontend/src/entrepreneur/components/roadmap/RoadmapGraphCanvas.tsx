import type { RoadmapItemRead } from "../../api/roadmapApi"
import StepNode from "./StepNode"
import { computeGroupLayout, NODE_HEIGHT, NODE_WIDTH, type GridViewMode } from "./roadmapLayout"

interface RoadmapGraphCanvasProps {
  items: RoadmapItemRead[]
  viewMode: GridViewMode
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
}

/**
 * Rendu visuel des nœuds d'un groupe : positions calculées par
 * `roadmapLayout.computeGroupLayout`, flèches de dépendance internes au
 * groupe en SVG. Les dépendances vers un autre groupe ne sont pas dessinées
 * ici (voir roadmapLayout, section sur les couches) — seul le popup de détail
 * les liste ("Étapes requises").
 */
export default function RoadmapGraphCanvas({ items, viewMode, selectedNodeId, onSelectNode }: RoadmapGraphCanvasProps) {
  const layout = computeGroupLayout(items, viewMode)
  const byId = new Map(items.map((item) => [item.node_id, item]))
  const canvasWidth = layout.width + NODE_WIDTH
  const canvasHeight = layout.height + NODE_HEIGHT

  return (
    <div className="relative overflow-x-auto py-2" style={{ minHeight: canvasHeight }}>
      <div className="relative" style={{ width: canvasWidth, height: canvasHeight }}>
        <svg className="pointer-events-none absolute left-0 top-0" width={canvasWidth} height={canvasHeight}>
          <defs>
            <marker
              id="roadmap-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
            </marker>
          </defs>
          {layout.edges.map((edge) => (
            <path
              key={`${edge.from}->${edge.to}`}
              d={edge.path}
              fill="none"
              stroke="#9ca3af"
              strokeWidth={1.5}
              markerEnd="url(#roadmap-arrow)"
            />
          ))}
        </svg>

        {layout.positions.map((pos) => {
          const item = byId.get(pos.nodeId)
          if (!item) return null
          return (
            <StepNode
              key={pos.nodeId}
              item={item}
              x={pos.x}
              y={pos.y}
              isSelected={selectedNodeId === pos.nodeId}
              onSelect={onSelectNode}
            />
          )
        })}
      </div>
    </div>
  )
}
