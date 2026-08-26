import { Link } from "react-router-dom"

interface ProjectSectionCardProps {
  to: string
  title: string
  description: string
  pendingCount: number
}

/** Card de la landing "Mon Projet" — une par section (Informations générales /
 * Informations légales / Vitrine publique). Le badge n'affiche que le nombre
 * de valeurs candidates en attente pour LA table de cette section (voir
 * utils/fieldValueTable.ts) — pas de badge du tout si ce nombre est à 0. */
export default function ProjectSectionCard({ to, title, description, pendingCount }: ProjectSectionCardProps) {
  return (
    <Link
      to={to}
      className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-5 transition hover:border-indigo-300 hover:shadow-sm"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {pendingCount > 0 && (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1.5 text-xs font-medium text-white">
            {pendingCount}
          </span>
        )}
      </div>
      <p className="text-xs text-gray-500">{description}</p>
    </Link>
  )
}
