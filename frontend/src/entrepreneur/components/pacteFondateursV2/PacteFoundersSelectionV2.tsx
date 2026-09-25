import { useState } from "react"
import type { ProjectAssociateRead } from "../../api/projectApi"

interface PacteFoundersSelectionV2Props {
  /** Déjà filtrés par l'appelant sur `est_partie_au_pacte_fondateurs === true`
   * — cet écran ne décide QUE qui, parmi eux, est Fondateur vs Investisseur. */
  associates: ProjectAssociateRead[]
  isSubmitting: boolean
  onConfirm: (fondateurIds: Set<string>) => void
}

/**
 * Écran v2 affiché juste après "Commencer la génération", avant la 1ère
 * section — remplace l'ancienne bannière passive "j'ai repris automatiquement
 * tes associés, corrige dans Équipe & capital si besoin" : plutôt que de
 * renvoyer l'utilisateur sur une autre page pour corriger `est_fondateur`
 * associé par associé, on le laisse choisir ici, dans le flux, pour tous les
 * associés d'un coup (voir discussion du 21/09/2026 — UX jugée trop lourde
 * sinon).
 *
 * `est_fondateur` reste un attribut persistant du projet (`project_associates`,
 * pas un état propre à cette session de génération) : la sélection validée
 * ici est écrite en base via `updateAssociateFondateur` (PATCH existant, un
 * appel par associé dont la valeur change) — PacteFondateursV2Page s'en
 * charge, ce composant ne fait que collecter le choix. Cette même case reste
 * aussi éditable depuis Équipe & capital (décision actée : garder les deux
 * points d'entrée, même source de vérité en base).
 *
 * Le propriétaire du projet (`linked_user_id !== null` — un seul associé par
 * projet porte ce champ, voir ProjectAssociate) est affiché verrouillé,
 * toujours coché, plutôt que proposé comme un choix ou masqué (discussion du
 * 24/09/2026) : repéré via `linked_user_id`, pas via `fonction_dirigeant ===
 * "Président"` (texte libre, pas fiable — deux associés pourraient porter le
 * même intitulé). Le masquer complètement aurait empêché l'utilisateur de
 * vérifier que son propre nom est bien inclus au pacte.
 */
export default function PacteFoundersSelectionV2({
  associates,
  isSubmitting,
  onConfirm,
}: PacteFoundersSelectionV2Props) {
  const owner = associates.find((a) => a.linked_user_id !== null) ?? null
  const selectableAssociates = associates.filter((a) => a.linked_user_id === null)

  const [selected, setSelected] = useState<Set<string>>(() => {
    const initial = new Set(associates.filter((a) => a.est_fondateur).map((a) => a.id))
    if (owner) initial.add(owner.id)
    return initial
  })

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function displayName(a: ProjectAssociateRead): string {
    return a.type_personne === "personne_morale"
      ? a.denomination_sociale || "(dénomination non renseignée)"
      : a.nom_complet
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold text-gray-900">Qui sont les fondateurs ?</h2>
        <p className="text-sm text-gray-600">
          Parmi les associés partie au pacte, sélectionne ceux qui sont Associés Fondateurs. Les
          autres seront listés comme Associés Investisseurs dans le préambule.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {owner && (
          <div className="flex items-center gap-3 rounded-lg border border-indigo-500 bg-indigo-50 p-3">
            <input type="checkbox" checked disabled className="h-4 w-4" />
            <span className="text-sm font-medium text-gray-900">
              {displayName(owner)}
              <span className="ml-2 text-xs font-normal text-indigo-700">
                Toi (propriétaire du projet) — toujours Associé Fondateur
              </span>
            </span>
          </div>
        )}

        {selectableAssociates.map((a) => (
          <label
            key={a.id}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 ${
              selected.has(a.id)
                ? "border-indigo-500 bg-indigo-50"
                : "border-gray-300 hover:border-gray-400"
            }`}
          >
            <input
              type="checkbox"
              checked={selected.has(a.id)}
              onChange={() => toggle(a.id)}
              className="h-4 w-4"
            />
            <span className="text-sm font-medium text-gray-900">{displayName(a)}</span>
          </label>
        ))}
      </div>

      {selected.size === 0 && (
        <p className="text-xs text-amber-600">
          Sélectionne au moins un fondateur pour continuer — sinon le préambule du pacte n'aura
          aucun Associé Fondateur.
        </p>
      )}

      <button
        type="button"
        disabled={isSubmitting || selected.size === 0}
        onClick={() => onConfirm(selected)}
        className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting ? "Enregistrement…" : "Continuer"}
      </button>
    </div>
  )
}
