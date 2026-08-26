/** Anneau de progression compact — remplace l'ancienne barre pleine largeur,
 * affiché à côté du titre de l'écran plutôt que sur sa propre ligne. Montre
 * `completion_percentage`, calculé côté backend (voir `_compute_completion`
 * dans project_service.py) — jamais recalculé ici. */
interface CircularProgressProps {
  percentage: number
  size?: number
}

export default function CircularProgress({ percentage, size = 40 }: CircularProgressProps) {
  const strokeWidth = 4
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference * (1 - percentage / 100)

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={strokeWidth} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#4f46e5"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-[stroke-dashoffset]"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-medium text-gray-700">
        {percentage}%
      </span>
    </div>
  )
}
