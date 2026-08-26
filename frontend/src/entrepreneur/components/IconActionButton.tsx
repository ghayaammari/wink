import type { ReactNode } from "react"

/** Chemins SVG (outline, style Heroicons) des 3 actions possibles sur un champ
 * extrait automatiquement — centralisés ici pour être réutilisés identiques
 * partout (écran 4, et le bloc `ExtractedFieldsReview` des écrans 5-9). */
export const ICON_PATH_CHECK = "m4.5 12.75 6 6 9-13.5"
export const ICON_PATH_PENCIL =
  "m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10"
export const ICON_PATH_CROSS = "M6 18 18 6M6 6l12 12"

const ICON_ACTION_VARIANT_CLASSES: Record<
  "default" | "primary" | "danger",
  string
> = {
  default:
    "border-gray-300 text-gray-700 hover:border-gray-400 hover:bg-gray-50",
  primary: "border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-700",
  danger: "border-gray-300 text-red-600 hover:border-red-300 hover:bg-red-50",
}

/** Bouton icône avec libellé affiché uniquement au survol (tooltip) — utilisé
 * partout où une action (Valider/Modifier/Ignorer/Annuler/Enregistrer) doit
 * apparaître sans texte visible en permanence, pour ne pas surcharger l'écran
 * quand plusieurs actions sont proposées côte à côte. */
export function IconActionButton({
  label,
  icon,
  onClick,
  disabled,
  variant = "default",
}: {
  label: string
  icon: ReactNode
  onClick: () => void
  disabled?: boolean
  variant?: "default" | "primary" | "danger"
}) {
  return (
    <div className="group relative">
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className={`rounded-lg border p-2 transition disabled:opacity-50 ${ICON_ACTION_VARIANT_CLASSES[variant]}`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className="h-5 w-5"
        >
          {icon}
        </svg>
      </button>
      <span className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
        {label}
      </span>
    </div>
  )
}
