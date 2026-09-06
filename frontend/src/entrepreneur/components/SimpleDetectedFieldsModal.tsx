import { useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  ignoreFieldValue,
  resolveFieldValue,
  type ProjectFieldValueRead,
} from "../api/projectApi"
import { encodeEditValue, formatForDisplay, type ExtractedFieldKind } from "../utils/fieldValueFormat"
import type { ExtractedFieldSpec } from "./ExtractedFieldsReview"

type ChoiceAction = "pending" | "accept" | "modify" | "ignore"
interface Choice {
  action: ChoiceAction
  /** Uniquement pour "modify" — texte brut affiché dans l'input. */
  value: string
}

interface SimpleDetectedFieldsModalProps {
  fields: ExtractedFieldSpec[]
  fieldValues: ProjectFieldValueRead[]
  /** Fournie par la page appelante — lit la valeur actuelle sur son propre
   * `legalProfile`/`publicProfile` (pas de table commune ici, contrairement à
   * `projects` pour DetectedFieldsModal). */
  currentValueLabel: (fieldName: string) => string
  projectId: string
  accessToken: string
  onClose: () => void
  onSaved: () => void
}

/**
 * Variante "sans project_type/stage" de DetectedFieldsModal.tsx — même
 * mécanisme (bold, Actuel/Détecté, Accepter/Modifier/Ignorer, rien envoyé
 * avant "Enregistrer") mais sans le couplage enum ni le contrôle de cohérence,
 * qui n'ont pas de sens pour `project_legal_profiles`/`project_public_profiles`
 * (pas de couple de champs interdépendants ici). Un fichier séparé plutôt que
 * de rendre DetectedFieldsModal générique avec des props optionnelles pour un
 * cas qui ne s'applique qu'à "Informations générales" — reste plus simple à
 * lire pour ces 2 pages, sans complexité qu'elles n'utilisent jamais.
 */
export default function SimpleDetectedFieldsModal({
  fields,
  fieldValues,
  currentValueLabel,
  projectId,
  accessToken,
  onClose,
  onSaved,
}: SimpleDetectedFieldsModalProps) {
  const specByName = new Map<string, ExtractedFieldSpec & { kind: ExtractedFieldKind }>(
    fields.map((f) => [f.fieldName, { ...f, kind: f.kind ?? "text" }]),
  )

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
          ? { action, value: prev[fv.id]?.value || formatForDisplay(fv.field_value, kind) }
          : { action, value: "" },
    }))
  }

  function setModifyValue(fv: ProjectFieldValueRead, value: string) {
    setChoices((prev) => ({ ...prev, [fv.id]: { action: "modify", value } }))
  }

  async function handleSave() {
    setError(null)
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
          if (choice.action === "ignore") return ignoreFieldValue(accessToken, projectId, fv.id)
          if (choice.action === "accept") {
            return resolveFieldValue(accessToken, projectId, fv.id, { validation_status: "confirme" })
          }
          return resolveFieldValue(accessToken, projectId, fv.id, {
            field_value: encodeEditValue(choice.value, kind),
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
          const choice = choiceFor(fv.id)
          const rawDetected = formatForDisplay(fv.field_value, spec.kind)
          const detectedLabel = spec.options
            ? (spec.options.find((o) => o.value === rawDetected)?.label ?? rawDetected)
            : rawDetected

          return (
            <div key={fv.id} className="flex flex-col gap-2 rounded-lg border border-gray-200 p-3">
              <p className="text-sm font-bold text-gray-900">{spec.label}</p>

              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <p className="text-xs text-gray-400">Actuel</p>
                  <p className="text-gray-700">{currentValueLabel(fv.field_name)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Détecté</p>
                  <p className="text-gray-900">{detectedLabel || "—"}</p>
                </div>
              </div>

              {choice.action === "modify" && (
                <div className="mt-1">
                  {spec.options ? (
                    <select
                      value={choice.value}
                      onChange={(e) => setModifyValue(fv, e.target.value)}
                      className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
                    >
                      {spec.options.map((o) => (
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
