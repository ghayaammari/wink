/**
 * Formatage/encodage des valeurs de `project_field_values`, partagés entre
 * ExtractedFieldsReview.tsx et DetectedFieldsModal.tsx — extrait pour éviter
 * que les deux composants divergent sur comment afficher/encoder une valeur
 * "liste" ou "booléen" (même bug de fond que projectStageOptions.ts).
 */
import { parseFieldValue } from "../api/projectApi"

export type ExtractedFieldKind = "text" | "number" | "list" | "boolean"

/** JSON brut (`field_value`) → texte affichable pour l'utilisateur. */
export function formatForDisplay(raw: string | null, kind: ExtractedFieldKind): string {
  const value = parseFieldValue(raw)
  if (kind === "list") return Array.isArray(value) ? value.join(", ") : ""
  if (kind === "boolean") return value === true ? "Oui" : value === false ? "Non" : "—"
  return String(value ?? "")
}

/** Texte saisi/édité par l'utilisateur → JSON prêt pour `field_value`
 * (le backend attend toujours du JSON, même pour un texte simple). */
export function encodeEditValue(raw: string, kind: ExtractedFieldKind): string {
  if (kind === "list") {
    const items = raw
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item.length > 0)
    return JSON.stringify(items)
  }
  if (kind === "boolean") return JSON.stringify(raw === "Oui")
  if (kind === "number") {
    const trimmed = raw.trim()
    return JSON.stringify(trimmed === "" ? null : Number(trimmed))
  }
  return JSON.stringify(raw)
}
