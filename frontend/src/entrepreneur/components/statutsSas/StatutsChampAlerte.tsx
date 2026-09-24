import { useState } from "react"
import type { RegleProbleme } from "../../api/documentGenerationApi"

interface Props {
  /** Problèmes de CE champ (déjà filtrés), le plus grave en premier. */
  problemes: RegleProbleme[]
  /** Remplit le champ avec la proposition conforme du garde-fou LLM. */
  onUtiliserProposition?: (texte: string) => void
}

/** Le plus grave d'abord : un blocage passe avant un avertissement. */
export function trierParGravite(problemes: RegleProbleme[]): RegleProbleme[] {
  return [...problemes].sort((a, b) => Number(a.gravite === "avertissement") - Number(b.gravite === "avertissement"))
}

/** Bordure du champ selon son problème le plus grave (vide si aucun). */
export function classeBordure(problemes: RegleProbleme[] | undefined): string {
  if (!problemes?.length) return ""
  return problemes.some((p) => p.gravite === "bloquant")
    ? "border-red-400 bg-red-50/40"
    : "border-amber-400 bg-amber-50/40"
}

/**
 * Alerte d'UN champ des statuts (garde-fou niveaux A et B, 24/09/2026),
 * affichée juste sous le champ concerné : une ligne courte, et « Détails »
 * pour le message complet, la base légale et, pour le contrôle juridique
 * LLM, une proposition conforme à appliquer en un clic.
 *
 * Court par défaut (retour utilisateur) : l'utilisateur voit tout de suite
 * QUOI corriger ; le POURQUOI n'est affiché que s'il le demande.
 */
export default function StatutsChampAlerte({ problemes, onUtiliserProposition }: Props) {
  const [ouvert, setOuvert] = useState(false)
  if (problemes.length === 0) return null

  const tries = trierParGravite(problemes)
  const principal = tries[0]
  const bloquant = principal.gravite === "bloquant"
  const couleur = bloquant ? "text-red-700" : "text-amber-700"

  return (
    <div className="flex flex-col gap-1 text-xs" role={bloquant ? "alert" : "status"}>
      <div className={`flex flex-wrap items-center gap-x-2 ${couleur}`}>
        <span>
          <span className="mr-1" aria-hidden>
            {bloquant ? "⛔" : "⚠️"}
          </span>
          {principal.message_court || principal.message}
          {tries.length > 1 && <span className="opacity-70"> (+{tries.length - 1})</span>}
        </span>
        <button
          type="button"
          onClick={() => setOuvert((o) => !o)}
          aria-expanded={ouvert}
          className="font-medium underline-offset-2 hover:underline"
        >
          {ouvert ? "Masquer ▴" : "Détails ▾"}
        </button>
      </div>

      {ouvert && (
        <div className="flex flex-col gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-gray-700">
          {tries.map((p, i) => (
            <div key={i} className="flex flex-col gap-1">
              <p>{p.message}</p>
              {p.base_legale && <p className="text-[11px] text-gray-500">{p.base_legale}</p>}
              {p.reformulation_proposee && (
                <div className="flex flex-col gap-1 rounded bg-gray-50 px-2 py-1.5">
                  <p className="text-[11px] font-medium text-gray-500">Proposition conforme</p>
                  <p className="whitespace-pre-wrap">{p.reformulation_proposee}</p>
                  {onUtiliserProposition && (
                    <button
                      type="button"
                      onClick={() => onUtiliserProposition(p.reformulation_proposee!)}
                      className="self-start rounded border border-indigo-200 bg-white px-2 py-1 text-[11px] font-medium text-indigo-700 hover:bg-indigo-50"
                    >
                      Utiliser cette proposition
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
