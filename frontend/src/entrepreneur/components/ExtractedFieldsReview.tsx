import { useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  ignoreFieldValue,
  resolveFieldValue,
  type ProjectFieldValueRead,
  type ProjectFieldValueUpdate,
} from "../api/projectApi"
import { encodeEditValue, formatForDisplay, type ExtractedFieldKind } from "../utils/fieldValueFormat"
import {
  ICON_PATH_CHECK,
  ICON_PATH_CROSS,
  ICON_PATH_PENCIL,
  IconActionButton,
} from "./IconActionButton"

export type { ExtractedFieldKind }

export interface ExtractedFieldSpec {
  /** Préfixé "table.colonne", ex: "projects.sector" — voir document_service.py. */
  fieldName: string
  label: string
  kind?: ExtractedFieldKind
  /** Si fourni, "Modifier" affiche une liste déroulante (ces valeurs) au lieu
   * d'un champ texte libre — pour un champ à choix fixes contraint par un
   * CHECK en base (ex: funding_visibility/compliance_visibility), même
   * raisonnement que project_type/stage dans DetectedFieldsModal.tsx, mais
   * générique ici plutôt que codé en dur par nom de champ. Non utilisé par
   * ExtractedFieldsReview lui-même pour l'instant (voir SimpleDetectedFieldsModal). */
  options?: { value: string; label: string }[]
}

export interface ExtractedFieldsReviewProps {
  fields: ExtractedFieldSpec[]
  /** Liste dans laquelle chercher les candidates pour `fields` — l'appelant la
   * fournit (au lieu d'un contexte interne) pour que ce composant reste
   * utilisable aussi bien dans le wizard d'onboarding que dans les pages de
   * "Mon Projet" (Informations générales/légales, Vitrine publique), qui
   * n'ont pas de contexte partagé entre elles. */
  fieldValues: ProjectFieldValueRead[]
  projectId: string
  accessToken: string
  /** Masque l'en-tête "Valeurs trouvées dans ton document" — utile quand ce
   * composant est instancié un champ à la fois (une ligne par champ, voir
   * "Mon Projet") plutôt qu'en bloc listant plusieurs champs d'un coup (écrans
   * d'onboarding). Par défaut affiché (comportement historique). */
  compact?: boolean
  /** Appelé après une résolution (confirmer/corriger) ou un ignorer réussi,
   * avec la liste mise à jour (candidate retirée) — à l'appelant de la stocker
   * et de rafraîchir ce qui dépend de la vraie colonne écrite (le composant ne
   * fait plus d'hypothèse sur "project" vs "profil légal" vs "profil public",
   * voir DECISIONS). */
  onFieldValuesChange: (fieldValues: ProjectFieldValueRead[]) => void
}

/** Bloc "valeurs trouvées dans ton document" pour un ou plusieurs champs
 * partageant une même liste de candidates. Composant purement présentationnel
 * côté données (tout vient de props) — seule la logique d'appel API
 * (résoudre/ignorer) reste interne, identique quelle que soit la table cible
 * (le endpoint `/projects/{id}/field-values/{field_value_id}` ne connaît pas
 * la table, juste un id de ligne `project_field_values`). */
export default function ExtractedFieldsReview({
  fields,
  fieldValues,
  projectId,
  accessToken,
  compact = false,
  onFieldValuesChange,
}: ExtractedFieldsReviewProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submittingId, setSubmittingId] = useState<string | null>(null)

  const specByName = new Map(fields.map((f) => [f.fieldName, f]))
  const pending = fieldValues.filter(
    (fv) =>
      specByName.has(fv.field_name) && fv.validation_status === "en_attente",
  )

  if (pending.length === 0) return null

  async function applyResolution(
    fv: ProjectFieldValueRead,
    data: ProjectFieldValueUpdate,
  ) {
    setError(null)
    setSubmittingId(fv.id)
    try {
      await resolveFieldValue(accessToken, projectId, fv.id, data)
      onFieldValuesChange(fieldValues.filter((v) => v.id !== fv.id))
      setEditingId(null)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Une erreur est survenue.",
      )
    } finally {
      setSubmittingId(null)
    }
  }

  async function handleIgnore(fv: ProjectFieldValueRead) {
    setError(null)
    setSubmittingId(fv.id)
    try {
      await ignoreFieldValue(accessToken, projectId, fv.id)
      onFieldValuesChange(fieldValues.filter((v) => v.id !== fv.id))
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Une erreur est survenue.",
      )
    } finally {
      setSubmittingId(null)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-indigo-200 bg-indigo-50/40 p-3">
      {!compact && (
        <p className="text-xs font-medium text-indigo-700">
          Valeurs trouvées dans ton document
        </p>
      )}

      {pending.map((fv) => {
        const spec = specByName.get(fv.field_name)!
        const kind = spec.kind ?? "text"
        const isEditing = editingId === fv.id
        const isSubmitting = submittingId === fv.id

        return (
          <div key={fv.id} className="flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              {!compact && <p className="text-xs text-gray-500">{spec.label}</p>}
              {isEditing ? (
                kind === "boolean" ? (
                  <div className="mt-1 flex gap-2">
                    {["Oui", "Non"].map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => setEditValue(option)}
                        className={`rounded-lg border px-3 py-1 text-sm font-medium transition ${
                          editValue === option
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
                    type={kind === "number" ? "number" : "text"}
                    min={kind === "number" ? 0 : undefined}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
                  />
                )
              ) : (
                <p className="truncate text-sm text-gray-900">
                  {formatForDisplay(fv.field_value, kind)}
                </p>
              )}
            </div>

            <div className="flex shrink-0 gap-1">
              {isEditing ? (
                <>
                  <IconActionButton
                    label="Annuler"
                    onClick={() => setEditingId(null)}
                    disabled={isSubmitting}
                    icon={
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={ICON_PATH_CROSS}
                      />
                    }
                  />
                  <IconActionButton
                    label="Enregistrer"
                    onClick={() =>
                      applyResolution(fv, {
                        field_value: encodeEditValue(editValue, kind),
                        validation_status: "corrige",
                      })
                    }
                    disabled={isSubmitting}
                    variant="primary"
                    icon={
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={ICON_PATH_CHECK}
                      />
                    }
                  />
                </>
              ) : (
                <>
                  <IconActionButton
                    label="Ignorer"
                    onClick={() => handleIgnore(fv)}
                    disabled={isSubmitting}
                    variant="danger"
                    icon={
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={ICON_PATH_CROSS}
                      />
                    }
                  />
                  <IconActionButton
                    label="Modifier"
                    onClick={() => {
                      setEditValue(formatForDisplay(fv.field_value, kind))
                      setEditingId(fv.id)
                    }}
                    disabled={isSubmitting}
                    icon={
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={ICON_PATH_PENCIL}
                      />
                    }
                  />
                  <IconActionButton
                    label="Valider"
                    onClick={() =>
                      applyResolution(fv, { validation_status: "confirme" })
                    }
                    disabled={isSubmitting}
                    variant="primary"
                    icon={
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d={ICON_PATH_CHECK}
                      />
                    }
                  />
                </>
              )}
            </div>
          </div>
        )
      })}

      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  )
}
