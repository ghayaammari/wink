import type { ReactNode } from "react"

interface FieldProps {
  label: string
  value: ReactNode
}

/** Paire label/valeur en lecture seule — brique de base des SectionCard des
 * pages dashboard (MyProjectPage, ProfilePage). Pas d'édition ici : voir
 * DECISIONS, un dashboard en lecture seule pour I0. */
export default function Field({ label, value }: FieldProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-gray-400">{label}</dt>
      <dd className="text-sm text-gray-900">{value}</dd>
    </div>
  )
}
