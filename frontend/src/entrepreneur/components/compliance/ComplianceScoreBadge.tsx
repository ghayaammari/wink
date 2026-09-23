/**
 * Affichage du score de conformité — un seul composant réutilisé par les 4
 * pages de diagnostic (RGPD, AI Act, HealthTech, FinTech), toutes
 * consommant le même schéma `ComplianceScoreRead` côté backend
 * (compliance_score_schemas.py). Composant purement présentationnel : ne
 * fait aucun appel réseau lui-même, chaque page garde son propre state et
 * son propre appel `get*Score`.
 */
interface ComplianceScoreBadgeProps {
  score: number | null
  totalObligations: number
}

export default function ComplianceScoreBadge({ score, totalObligations }: ComplianceScoreBadgeProps) {
  // Rien à afficher tant qu'aucune obligation n'existe (pas encore de
  // diagnostic généré) — évite une barre à 0% trompeuse avant même que
  // l'entrepreneur ait lancé quoi que ce soit.
  if (totalObligations === 0 || score === null) {
    return null
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3">
      <span className="whitespace-nowrap text-sm font-medium text-gray-700">Score de conformité</span>
      <div className="h-2 flex-1 max-w-[10rem] overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-indigo-600 transition-[width]"
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="whitespace-nowrap text-sm font-semibold text-gray-900">{score}%</span>
    </div>
  )
}
