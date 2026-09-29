import { Link } from "react-router-dom"

interface ProjectSectionCardProps {
  to: string
  title: string
  description: string
  pendingCount: number
  // Score de conformité (0-100), optionnel — seule CompliancePlanPage
  // l'utilise (RGPD/AI Act/secteur). `undefined` (comportement par défaut,
  // MyProjectPage) : rien affiché. `null` : diagnostic pas encore généré,
  // rien affiché non plus (voir ComplianceScoreBadge, même règle). Un
  // second badge, distinct de pendingCount (sémantique différente : ici un
  // pourcentage de complétude, pas un compteur de valeurs en attente).
  scorePercent?: number | null
}

/** Card de la landing "Mon Projet" / "Conformité" — une par section. Le

 * badge `pendingCount` n'affiche que le nombre de valeurs candidates en
 * attente pour LA table de cette section (voir utils/fieldValueTable.ts) —
 * pas de badge du tout si ce nombre est à 0. Le badge `scorePercent`, s'il
 * est fourni et non nul, s'affiche à côté (voir prop ci-dessus). */
export default function ProjectSectionCard({ to, title, description, pendingCount, scorePercent }: ProjectSectionCardProps) {
  return (
    <Link
      to={to}
      className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-5 transition hover:-translate-y-0.5 hover:border-wink-300 hover:shadow-md"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        <div className="flex items-center gap-1.5">
          {scorePercent !== undefined && scorePercent !== null && (
            <span className="flex h-5 items-center justify-center rounded-full bg-wink-50 px-2 text-xs font-semibold text-wink-700">
              {scorePercent}%
            </span>
          )}
          {pendingCount > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-wink-600 px-1.5 text-xs font-medium text-white">
              {pendingCount}
            </span>
          )}
        </div>
      </div>
      <p className="text-xs text-gray-500">{description}</p>
    </Link>
  )
}
