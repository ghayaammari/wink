import { Link } from "react-router-dom"
import type { ProblemeAnnonce } from "../../api/legalAnnouncementApi"
import { PAGES_CORRECTION } from "./annoncePages"

interface Props {
  problemes: ProblemeAnnonce[]
  /** "bloquant" : rien ne peut être généré tant qu'il en reste ; "avertissement" : informatif. */
  gravite: "bloquant" | "avertissement"
}

/**
 * Liste des problèmes de l'annonce, regroupés par page à corriger, avec un
 * lien « Compléter → » — même présentation que l'écran « Avant de commencer »
 * des statuts, pour que l'entrepreneur retrouve le même geste.
 */
export default function AnnonceProblemesList({ problemes, gravite }: Props) {
  if (problemes.length === 0) return null
  const bloquant = gravite === "bloquant"
  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border p-4 ${
        bloquant ? "border-amber-200 bg-amber-50" : "border-orange-200 bg-orange-50"
      }`}
    >
      <p className={`text-sm font-semibold ${bloquant ? "text-amber-900" : "text-orange-900"}`}>
        {bloquant ? "Avant de rédiger votre annonce" : "À vérifier"}
      </p>
      {PAGES_CORRECTION.map(({ page, titre, lien }) => {
        const duGroupe = problemes.filter((p) => p.page === page)
        if (duGroupe.length === 0) return null
        return (
          <section key={page} className="flex flex-col gap-1 rounded-md bg-white/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-600">{titre}</h3>
              {lien && (
                <Link
                  to={lien}
                  className="rounded-lg border border-indigo-300 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                >
                  Compléter →
                </Link>
              )}
            </div>
            <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-gray-700">
              {duGroupe.map((p) => (
                <li key={p.code}>{p.message}</li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}
