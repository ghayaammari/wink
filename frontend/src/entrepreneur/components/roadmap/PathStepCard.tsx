import type { RoadmapItemRead } from "../../api/roadmapApi"
import { PATH_ROW_HEIGHT } from "./roadmapLayout"

interface PathStepCardProps {
  item: RoadmapItemRead
  x: number
  y: number
  width: number
  isSelected: boolean
  onSelect: (nodeId: string) => void
}

const STATUT_META: Record<
  string,
  { label: string; dot: string; title: string; italic: boolean; background: string; border: string }
> = {
  verrouille: {
    label: "Verrouillé",
    dot: "#9ca3af",
    title: "#9ca3af",
    italic: true,
    background: "#f9fafb",
    border: "1px solid #e5e7eb",
  },
  a_faire: {
    label: "À faire",
    dot: "#6b7280",
    title: "#111827",
    italic: false,
    background: "#ffffff",
    border: "1px solid #d1d5db",
  },
  en_cours: {
    label: "En cours",
    dot: "#4f46e5",
    title: "#111827",
    italic: false,
    background: "#eef2ff",
    border: "1.5px solid #4f46e5",
  },
  termine: {
    label: "Terminé",
    dot: "#059669",
    title: "#6b7280",
    italic: false,
    background: "#ffffff",
    border: "1px solid #e5e7eb",
  },
  non_necessaire: {
    label: "Non applicable",
    dot: "#9ca3af",
    title: "#9ca3af",
    italic: true,
    background: "#f9fafb",
    border: "1px dashed #d1d5db",
  },
}

/**
 * Carte de nœud pour la vue "Parcours" (RoadmapPathView) — visuel distinct
 * du "chip" compact des vues Graphe/Sentier (voir StepNode) : icône de
 * statut + libellé + titre, dans le style du mockup de référence
 * (verrou/coche/pastille, bordure et fond selon le statut). Composant séparé
 * plutôt qu'une variante de StepNode à coups de props conditionnelles : les
 * deux vues ont des besoins visuels différents, les mélanger dans un seul
 * composant aurait mélangé deux responsabilités.
 */
export default function PathStepCard({ item, x, y, width, isSelected, onSelect }: PathStepCardProps) {
  const meta = STATUT_META[item.statut] ?? STATUT_META.verrouille
  const isLocked = item.statut === "verrouille"
  const isDone = item.statut === "termine"

  return (
    <button
      type="button"
      onClick={() => onSelect(item.node_id)}
      style={{
        left: x,
        top: y,
        width,
        minHeight: PATH_ROW_HEIGHT,
        background: meta.background,
        border: meta.border,
        boxShadow: isSelected ? "0 0 0 2px #4f46e5, 0 6px 14px rgba(17,24,39,0.08)" : "0 1px 2px rgba(17,24,39,0.04)",
      }}
      className="absolute flex flex-col gap-1.5 rounded-lg p-3.5 text-left transition-shadow"
    >
      <span className="flex items-center gap-1.5">
        {isLocked && (
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke={meta.dot}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="5" y="11" width="14" height="10" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
        )}
        {isDone && (
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke={meta.dot}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        )}
        {!isLocked && !isDone && <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: meta.dot }} />}
        <span className="text-[10px] font-semibold uppercase tracking-wide" style={{ color: meta.dot }}>
          {meta.label}
        </span>
      </span>
      <span
        className="text-[13px] font-medium leading-snug"
        style={{ color: meta.title, fontStyle: meta.italic ? "italic" : "normal" }}
      >
        {item.node_snapshot.nom}
      </span>
    </button>
  )
}
