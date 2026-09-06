import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  ignoreFieldValue,
  parseFieldValue,
  resolveFieldValue,
  type ProjectFieldValueRead,
} from "../api/projectApi"

export interface ConflictOption {
  value: string
  label: string
}

export interface FieldConflictReviewProps {
  /** Préfixé "table.colonne", ex: "projects.project_type". */
  fieldName: string
  currentValue: string
  currentLabel: string
  /** Choix fixes uniquement — jamais de texte libre pour ces champs (voir
   * docstring plus bas). */
  options: ConflictOption[]
  fieldValues: ProjectFieldValueRead[]
  projectId: string
  accessToken: string
  onResolved: () => void
  /** Signale au parent la valeur actuellement sélectionnée dans le dropdown —
   * avant même que "Appliquer" soit cliqué. Sert à coupler `project_type` et
   * `stage` (voir ProjectGeneralInfoPage.tsx) : changer le type doit filtrer
   * les stades valides pour l'autre champ, en direct. */
  onSelectionChange?: (value: string) => void
  /** Désactive le select et les 2 boutons sans cacher le composant — utilisé
   * pour `stage` tant qu'un conflit sur `project_type` n'est pas réglé (voir
   * ProjectGeneralInfoPage.tsx) : le stade affiché dépend d'un type qui n'est
   * pas encore confirmé, pas question de le modifier avant. */
  disabled?: boolean
}

/**
 * Variante d'ExtractedFieldsReview pour les champs à choix fixes et à fort
 * impact structurel (`projects.project_type`, `projects.stage`) : liste
 * déroulante au lieu d'un champ texte (évite d'écrire une valeur hors enum),
 * et affiché uniquement en cas de VRAI désaccord — jamais pour un premier
 * remplissage, ces 2 champs étant toujours déjà renseignés depuis l'écran 2
 * de l'onboarding. Le backend (document_service.upload_and_extract) ne crée
 * même pas de candidate quand elle confirme la valeur déjà en base ; le
 * garde-fou `candidateValue === currentValue` ci-dessous n'est qu'une
 * sécurité côté client si jamais une candidate obsolète traîne encore.
 */
export default function FieldConflictReview({
  fieldName,
  currentValue,
  currentLabel,
  options,
  fieldValues,
  projectId,
  accessToken,
  onResolved,
  onSelectionChange,
  disabled = false,
}: FieldConflictReviewProps) {
  const candidate = fieldValues.find(
    (fv) => fv.field_name === fieldName && fv.validation_status === "en_attente",
  )
  const candidateValue = candidate ? String(parseFieldValue(candidate.field_value) ?? "") : null
  const [selected, setSelected] = useState(candidateValue ?? currentValue)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Avant tout early return : les hooks doivent toujours s'exécuter dans le même
  // ordre. Prévient le parent de la sélection courante même si ce composant n'a
  // finalement rien à afficher (pas de conflit) — le parent reçoit alors la
  // valeur actuelle du champ, ce qui est le bon défaut.
  useEffect(() => {
    onSelectionChange?.(selected)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne signaler que le changement de `selected`
  }, [selected])

  if (!candidate || candidateValue === currentValue) return null

  async function apply() {
    setError(null)
    setIsSubmitting(true)
    try {
      await resolveFieldValue(accessToken, projectId, candidate!.id, {
        field_value: JSON.stringify(selected),
        validation_status: selected === candidateValue ? "confirme" : "corrige",
      })
      onResolved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function keepCurrent() {
    setError(null)
    setIsSubmitting(true)
    try {
      await ignoreFieldValue(accessToken, projectId, candidate!.id)
      onResolved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const candidateLabel = options.find((o) => o.value === candidateValue)?.label ?? candidateValue

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3">
      <p className="text-xs font-medium text-amber-800">
        ⚠ Incohérence détectée — le document indique "{candidateLabel}", alors que tu as
        renseigné "{currentLabel}".
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={isSubmitting || disabled}
          className="rounded-lg border border-gray-300 px-2 py-1 text-sm disabled:opacity-50"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={apply}
          disabled={isSubmitting || disabled}
          className="rounded-lg bg-indigo-600 px-3 py-1 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          Appliquer
        </button>
        <button
          type="button"
          onClick={keepCurrent}
          disabled={isSubmitting || disabled}
          className="rounded-lg border border-gray-300 px-3 py-1 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          Garder "{currentLabel}"
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
