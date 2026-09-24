import { useState } from "react"
import type { CompanyOfficerRead, ProjectAssociateRead } from "../../api/projectApi"
import { nomDirigeant } from "./officerRoles"

interface Props {
  officer: CompanyOfficerRead
  associes: ProjectAssociateRead[]
  onEdit: () => void
  /** Rejette en cas d'échec : la ligne affiche alors l'erreur. */
  onDelete: () => Promise<void>
}

/**
 * Une ligne de la page Dirigeants : nom, étiquette Associé/Externe, durée,
 * boutons Modifier / Supprimer. La suppression se confirme DANS la ligne
 * (pas de popup système, qui bloque la page et casse le flux).
 */
export default function OfficerRow({ officer, associes, onEdit, onDelete }: Props) {
  const [confirmation, setConfirmation] = useState(false)
  const [suppressionEnCours, setSuppressionEnCours] = useState(false)
  const [erreur, setErreur] = useState<string | null>(null)

  const nom = nomDirigeant(officer, associes)
  const estSociete = officer.type_personne === "personne_morale"

  async function supprimer() {
    setSuppressionEnCours(true)
    setErreur(null)
    try {
      await onDelete()
    } catch {
      setErreur("La suppression a échoué. Réessayez.")
      setSuppressionEnCours(false)
      setConfirmation(false)
    }
  }

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span aria-hidden className="text-base">{estSociete ? "🏢" : "👤"}</span>
          <span className="truncate text-sm font-medium text-gray-900">{nom}</span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
              officer.associate_id ? "bg-indigo-50 text-indigo-700" : "bg-gray-200 text-gray-700"
            }`}
          >
            {officer.associate_id ? "Associé" : "Externe"}
          </span>
          {officer.duree_fonctions && (
            <span className="truncate text-xs text-gray-500">· {officer.duree_fonctions}</span>
          )}
        </div>

        {confirmation ? (
          <div className="flex shrink-0 items-center gap-2 text-xs">
            <span className="text-gray-700">Supprimer {nom} ?</span>
            <button
              type="button"
              onClick={supprimer}
              disabled={suppressionEnCours}
              className="rounded-md bg-red-600 px-2 py-1 font-medium text-white hover:bg-red-500 disabled:opacity-50"
            >
              {suppressionEnCours ? "…" : "Oui"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmation(false)}
              disabled={suppressionEnCours}
              className="rounded-md border border-gray-300 px-2 py-1 text-gray-700 hover:border-gray-400"
            >
              Non
            </button>
          </div>
        ) : (
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={onEdit}
              className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:border-gray-400"
            >
              ✏ Modifier
            </button>
            <button
              type="button"
              onClick={() => setConfirmation(true)}
              aria-label={`Supprimer ${nom}`}
              className="rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:border-red-300 hover:text-red-600"
            >
              🗑
            </button>
          </div>
        )}
      </div>
      {erreur && <p className="text-xs text-red-600">{erreur}</p>}
    </div>
  )
}
