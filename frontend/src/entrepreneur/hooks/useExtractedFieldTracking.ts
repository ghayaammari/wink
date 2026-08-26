import { useMemo, useState } from "react"
import type {
  FieldValueResolution,
  ProjectFieldValueRead,
} from "../api/projectApi"

/**
 * Suit, pour un écran donné, l'état des champs extraits en attente
 * (`en_attente`) affichés inline dans le formulaire habituel (voir
 * `components/ExtractedFieldFrame.tsx`) : quels champs l'utilisateur a
 * ignorés, quels champs il a modifiés. N'importe quelle interaction sur un
 * champ (frappe, clic bouton) = "touché" — jamais déduit en comparant la
 * valeur soumise à la valeur extraite (voir DECISIONS "pas de devinette côté
 * backend" : le frontend sait déjà ce qu'il s'est passé au moment du clic).
 *
 * `pendingFieldNames` = les `field_name` ("table.colonne") que CET écran
 * affiche, pour filtrer `fieldValues` du contexte à ce qui le concerne.
 */
export function useExtractedFieldTracking(
  fieldValues: ProjectFieldValueRead[],
  pendingFieldNames: string[],
) {
  const pendingByField = useMemo(() => {
    const names = new Set(pendingFieldNames)
    const map = new Map<string, ProjectFieldValueRead>()
    for (const fv of fieldValues) {
      if (names.has(fv.field_name) && fv.validation_status === "en_attente") {
        map.set(fv.field_name, fv)
      }
    }
    return map
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fieldValues, pendingFieldNames.join(",")])

  const [ignored, setIgnored] = useState<Set<string>>(new Set())
  const [touched, setTouched] = useState<Set<string>>(new Set())

  /** Le cadre encadrant le champ (bordure + note) reste affiché tant que le
   * champ a une valeur extraite en attente et n'a pas été ignoré — même après
   * modification, pour garder la trace visuelle que la valeur vient du
   * document. Seule l'icône Ignorer disparaît dès que l'utilisateur touche le
   * champ (voir `isTouched`) : une fois qu'il tape sa propre valeur, "ignorer
   * la valeur extraite" n'a plus de sens — il l'a déjà remplacée. */
  function isActive(fieldName: string): boolean {
    return pendingByField.has(fieldName) && !ignored.has(fieldName)
  }

  function isTouched(fieldName: string): boolean {
    return touched.has(fieldName)
  }

  function markTouched(fieldName: string): void {
    if (!pendingByField.has(fieldName)) return
    setTouched((prev) => {
      if (prev.has(fieldName)) return prev
      const next = new Set(prev)
      next.add(fieldName)
      return next
    })
  }

  function ignore(fieldName: string): void {
    setIgnored((prev) => {
      const next = new Set(prev)
      next.add(fieldName)
      return next
    })
  }

  /** À appeler au submit : construit `resolved_field_values` pour le payload
   * PATCH/POST. Un champ resté en attente, ni ignoré ni touché, est envoyé
   * comme "confirmé tel quel" — le laisser inchangé EST la confirmation. */
  function buildResolutions(): FieldValueResolution[] {
    const resolutions: FieldValueResolution[] = []
    for (const [fieldName, fv] of pendingByField) {
      if (ignored.has(fieldName)) {
        resolutions.push({ id: fv.id, action: "ignore" })
      } else if (touched.has(fieldName)) {
        resolutions.push({ id: fv.id, action: "corrige" })
      } else {
        resolutions.push({ id: fv.id, action: "confirme" })
      }
    }
    return resolutions
  }

  return {
    pendingByField,
    isActive,
    isTouched,
    markTouched,
    ignore,
    buildResolutions,
  }
}
