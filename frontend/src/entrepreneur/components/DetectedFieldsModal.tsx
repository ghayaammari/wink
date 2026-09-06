import { useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  ignoreFieldValue,
  parseFieldValue,
  resolveFieldValue,
  type ProjectFieldValueRead,
  type ProjectRead,
} from "../api/projectApi"
import { encodeEditValue, formatForDisplay, type ExtractedFieldKind } from "../utils/fieldValueFormat"
import { currentValueLabel } from "../utils/projectFieldCurrentValue"
import { PROJECT_TYPE_OPTIONS, STAGE_LABELS, isStageValidFor, stageOptionsFor } from "../utils/projectStageOptions"
import type { ExtractedFieldSpec } from "./ExtractedFieldsReview"

const TYPE_FIELD = "projects.project_type"
const STAGE_FIELD = "projects.stage"

type ChoiceAction = "pending" | "accept" | "modify" | "ignore"
interface Choice {
  action: ChoiceAction
  /** Uniquement pour "modify" — texte brut affiché dans l'input/select. */
  value: string
}

interface DetectedFieldsModalProps {
  project: ProjectRead
  /** Les 10 champs "texte" de la page (hors project_type/stage). */
  fields: ExtractedFieldSpec[]
  fieldValues: ProjectFieldValueRead[]
  accessToken: string
  onClose: () => void
  /** Appelé après un enregistrement réussi — le parent recharge `project`/`fieldValues`. */
  onSaved: () => void
}

/**
 * Popup unique "Consulter les informations détectées" — remplace les usages
 * inline d'ExtractedFieldsReview (10 champs texte) ET de FieldConflictReview
 * (project_type/stage) sur "Informations générales" : un seul endroit pour
 * voir toutes les candidates en attente et choisir Accepter/Modifier/Ignorer
 * par champ, MAIS rien n'est envoyé au backend avant "Enregistrer" (contraste
 * avec ExtractedFieldsReview/FieldConflictReview, qui appelaient l'API
 * immédiatement à chaque clic — voir DECISIONS pour le choix de ce nouveau
 * mécanisme "batch").
 *
 * Un champ jamais touché (`pending`) est exclu de la requête d'enregistrement :
 * sa candidate reste `en_attente`, aucun appel API n'est fait pour lui.
 *
 * project_type/stage utilisent un <select> (jamais de texte libre, même
 * logique que FieldConflictReview) et sont soumis à un contrôle de cohérence
 * calculé à partir du résultat EFFECTIF de chaque champ (valeur actuelle si
 * pending/ignore, valeur détectée si accept, valeur choisie si modify) au
 * moment de cliquer "Enregistrer" — bloquant avec une erreur inline si le
 * couple obtenu est incohérent, jamais corrigé silencieusement à leur place.
 */
export default function DetectedFieldsModal({
  project,
  fields,
  fieldValues,
  accessToken,
  onClose,
  onSaved,
}: DetectedFieldsModalProps) {
  const specByName = new Map<string, { label: string; kind: ExtractedFieldKind }>(
    fields.map((f) => [f.fieldName, { label: f.label, kind: f.kind ?? "text" }]),
  )
  specByName.set(TYPE_FIELD, { label: "Startup", kind: "text" })
  specByName.set(STAGE_FIELD, { label: "Stade financier", kind: "text" })

  const pending = fieldValues.filter(
    (fv) => specByName.has(fv.field_name) && fv.validation_status === "en_attente",
  )

  const [choices, setChoices] = useState<Record<string, Choice>>({})
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function choiceFor(id: string): Choice {
    return choices[id] ?? { action: "pending", value: "" }
  }

  function setAction(fv: ProjectFieldValueRead, action: ChoiceAction) {
    setError(null)
    const kind = specByName.get(fv.field_name)!.kind
    setChoices((prev) => ({
      ...prev,
      [fv.id]:
        action === "modify"
          ? {
              action,
              // Pré-remplit avec la valeur détectée pour éviter un champ vide —
              // l'utilisateur ajuste plutôt que de retaper depuis zéro.
              value: prev[fv.id]?.value || formatForDisplay(fv.field_value, kind),
            }
          : { action, value: "" },
    }))
  }

  function setModifyValue(fv: ProjectFieldValueRead, value: string) {
    setChoices((prev) => ({ ...prev, [fv.id]: { action: "modify", value } }))
  }

  /** Valeur "brute" (string) que le champ aurait dans `projects` une fois cette
   * modale enregistrée, compte tenu du choix courant sur sa candidate. */
  function effectiveValue(fieldName: string, currentValue: string): string {
    const candidate = pending.find((fv) => fv.field_name === fieldName)
    if (!candidate) return currentValue
    const choice = choiceFor(candidate.id)
    if (choice.action === "accept") return String(parseFieldValue(candidate.field_value) ?? "")
    if (choice.action === "modify") return choice.value
    return currentValue
  }

  async function handleSave() {
    setError(null)

    const resultType = effectiveValue(TYPE_FIELD, project.project_type)
    const resultStage = effectiveValue(STAGE_FIELD, project.stage)
    if (!isStageValidFor(resultType, resultStage)) {
      const typeLabel = PROJECT_TYPE_OPTIONS.find((o) => o.value === resultType)?.label ?? resultType
      const validLabels = stageOptionsFor(resultType)
        .map((o) => o.label)
        .join(", ")
      setError(
        `Le couple "${typeLabel}" / "${STAGE_LABELS[resultStage] ?? resultStage}" n'est pas cohérent. ` +
          `Pour "${typeLabel}", choisis parmi : ${validLabels}.`,
      )
      return
    }

    const touched = pending.filter((fv) => choiceFor(fv.id).action !== "pending")
    if (touched.length === 0) {
      onClose()
      return
    }

    setIsSubmitting(true)
    try {
      await Promise.all(
        touched.map((fv) => {
          const choice = choiceFor(fv.id)
          const kind = specByName.get(fv.field_name)!.kind
          if (choice.action === "ignore") return ignoreFieldValue(accessToken, project.id, fv.id)
          if (choice.action === "accept") {
            return resolveFieldValue(accessToken, project.id, fv.id, { validation_status: "confirme" })
          }
          // "modify" — project_type/stage envoient directement la valeur d'enum
          // choisie (déjà une valeur "brute", pas de virgules/booléen à encoder).
          const encoded =
            fv.field_name === TYPE_FIELD || fv.field_name === STAGE_FIELD
              ? JSON.stringify(choice.value)
              : encodeEditValue(choice.value, kind)
          return resolveFieldValue(accessToken, project.id, fv.id, {
            field_value: encoded,
            validation_status: "corrige",
          })
        }),
      )
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (pending.length === 0) {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">Aucune information détectée en attente pour l'instant.</p>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
          >
            Fermer
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        {pending.map((fv) => {
          const spec = specByName.get(fv.field_name)!
          const isTypeOrStage = fv.field_name === TYPE_FIELD || fv.field_name === STAGE_FIELD
          const choice = choiceFor(fv.id)
          const currentLabel = currentValueLabel(project, fv.field_name)
          const detectedRaw = String(parseFieldValue(fv.field_value) ?? "")
          const detectedLabel = isTypeOrStage
            ? fv.field_name === TYPE_FIELD
              ? PROJECT_TYPE_OPTIONS.find((o) => o.value === detectedRaw)?.label ?? detectedRaw
              : STAGE_LABELS[detectedRaw] ?? detectedRaw
            : formatForDisplay(fv.field_value, spec.kind)

          // Pour project_type/stage : options du <select> "Modifier" — le stade
          // se filtre selon le project_type EFFECTIF actuel (voir effectiveValue),
          // pour guider le choix, sans empêcher une combinaison encore incohérente
          // (le blocage réel se fait à "Enregistrer", pas ici).
          const dropdownOptions =
            fv.field_name === TYPE_FIELD
              ? PROJECT_TYPE_OPTIONS
              : fv.field_name === STAGE_FIELD
                ? stageOptionsFor(effectiveValue(TYPE_FIELD, project.project_type))
                : []

          return (
            <div key={fv.id} className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3">
              <p className="text-sm font-bold text-gray-900">{spec.label}</p>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-400">Actuel</p>
                  <p className="text-gray-700">{currentLabel}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Détecté</p>
                  <p className="text-gray-900">{detectedLabel || "—"}</p>
                </div>
              </div>

              {choice.action === "modify" && (
                <div className="mt-1">
                  {isTypeOrStage ? (
                    <select
                      value={choice.value}
                      onChange={(e) => setModifyValue(fv, e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
                    >
                      {dropdownOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  ) : spec.kind === "boolean" ? (
                    <div className="flex gap-2">
                      {["Oui", "Non"].map((option) => (
                        <button
                          key={option}
                          type="button"
                          onClick={() => setModifyValue(fv, option)}
                          className={`rounded-lg border px-3 py-1 text-sm font-medium transition ${
                            choice.value === option
                              ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                              : "border-gray-300 text-gray-700 hover:border-gray-400"
                          }`}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <input
                      type={spec.kind === "number" ? "number" : "text"}
                      min={spec.kind === "number" ? 0 : undefined}
                      value={choice.value}
                      onChange={(e) => setModifyValue(fv, e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
                    />
                  )}
                </div>
              )}

              <div className="mt-1 flex flex-wrap gap-2">
                {(["accept", "modify", "ignore"] as const).map((action) => {
                  const isActive = choice.action === action
                  const labels: Record<typeof action, string> = {
                    accept: "Accepter",
                    modify: "Modifier",
                    ignore: "Ignorer",
                  }
                  return (
                    <button
                      key={action}
                      type="button"
                      onClick={() => setAction(fv, action)}
                      className={`rounded-lg border px-3 py-1 text-xs font-medium transition ${
                        isActive
                          ? action === "ignore"
                            ? "border-red-400 bg-red-50 text-red-700"
                            : "border-indigo-600 bg-indigo-50 text-indigo-700"
                          : "border-gray-300 text-gray-700 hover:border-gray-400"
                      }`}
                    >
                      {labels[action]}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </div>
  )
}
