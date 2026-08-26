/**
 * Conversion des valeurs extraites (`project_field_values.field_value`, toujours
 * du JSON — voir document_service.py, même pour un texte simple) vers le
 * type/format attendu par l'input du formulaire habituel qu'elles préremplissent
 * (pattern inline, voir `components/ExtractedFieldFrame.tsx`).
 */
import { parseFieldValue, type ProjectFieldValueRead } from "../api/projectApi"

export function extractedText(raw: string | null): string {
  const value = parseFieldValue(raw)
  return typeof value === "string" ? value : ""
}

export function extractedListText(raw: string | null): string {
  const value = parseFieldValue(raw)
  return Array.isArray(value) ? value.map(String).join(", ") : ""
}

export function extractedNumberText(raw: string | null): string {
  const value = parseFieldValue(raw)
  return typeof value === "number" ? String(value) : ""
}

export function extractedBoolean(raw: string | null): boolean | null {
  const value = parseFieldValue(raw)
  return typeof value === "boolean" ? value : null
}

/** Valeur initiale d'un champ du formulaire : la valeur extraite en attente si
 * elle existe pour ce champ sur cet écran, sinon la valeur déjà stockée sur le
 * projet/profil (`fallback`). N'a de sens que si aucun brouillon localStorage
 * n'existe déjà pour cet écran — le brouillon est prioritaire, voir
 * `formDraft.ts` et son usage dans chaque écran. */
export function initialFieldValue<T>(
  pendingByField: Map<string, ProjectFieldValueRead>,
  fieldName: string,
  extract: (raw: string | null) => T,
  fallback: T,
): T {
  const pending = pendingByField.get(fieldName)
  return pending ? extract(pending.field_value) : fallback
}
