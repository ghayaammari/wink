import type { ReactNode } from "react"

interface SectionCardProps {
  title: string
  children: ReactNode
  action?: ReactNode
}

/**
 * Carte de section en lecture seule pour les pages dashboard (ex:
 * MyProjectPage, ProfilePage) — un seul composant pour garder un style
 * cohérent entre sections plutôt que répéter la même bordure/padding dans
 * chaque bloc à chaque nouvel écran de dashboard.
 */
export default function SectionCard({ title, children, action }: SectionCardProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}
