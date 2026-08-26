import type { ReactNode } from "react"
import { ICON_PATH_CROSS, IconActionButton } from "./IconActionButton"

/**
 * Encadre un champ du formulaire habituel dont la valeur vient d'un document
 * importé (pattern "inline" — remplace l'ancien bloc séparé
 * `ExtractedFieldsReview` pour les écrans 4 à 9, voir DECISIONS). Actif tant
 * que l'utilisateur n'a pas cliqué "Ignorer" pour ce champ : éditer directement
 * la valeur EST "modifier", la laisser telle quelle EST "confirmer" — plus
 * besoin d'icônes Modifier/Valider séparées (voir
 * `hooks/useExtractedFieldTracking.ts`).
 *
 * `touched` masque l'icône Ignorer dès la première interaction (frappe, clic)
 * — une fois que l'utilisateur a commencé à remplacer la valeur lui-même,
 * "ignorer la valeur extraite" n'a plus de sens. Le cadre (bordure + note)
 * reste affiché : il garde la trace visuelle que ce champ était pré-rempli.
 */
export function ExtractedFieldFrame({
  active,
  touched,
  onIgnore,
  children,
}: {
  active: boolean
  touched: boolean
  onIgnore: () => void
  children: ReactNode
}) {
  if (!active) return <>{children}</>

  return (
    <div className="rounded-lg border border-indigo-200 bg-indigo-50/40 p-2">
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-indigo-700">
          Valeur trouvée dans ton document
        </p>
        {!touched && (
          <IconActionButton
            label="Ignorer"
            onClick={onIgnore}
            variant="danger"
            icon={
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d={ICON_PATH_CROSS}
              />
            }
          />
        )}
      </div>
      {children}
    </div>
  )
}
