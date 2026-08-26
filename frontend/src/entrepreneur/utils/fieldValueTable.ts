/**
 * `field_name` est toujours préfixé "table.colonne" (voir document_service.py
 * côté backend, ex: "project_legal_profiles.siret") — ces fonctions en
 * extraient la table cible pour grouper les candidates par section de "Mon
 * Projet" (Informations générales / légales, Vitrine publique).
 */
import type { ProjectFieldValueRead } from "../api/projectApi"

export function fieldValueTable(fieldName: string): string {
  return fieldName.split(".", 1)[0]
}

/** Compte les candidates en attente (`en_attente`) par table — utilisé pour
 * les badges de la landing "Mon Projet". Une candidate déjà confirmée/corrigée
 * ne compte pas : elle n'a plus de raison d'apparaître (voir
 * document_service.py, resolve_field_value/apply_resolutions). */
export function countPendingByTable(fieldValues: ProjectFieldValueRead[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const fv of fieldValues) {
    if (fv.validation_status !== "en_attente") continue
    const table = fieldValueTable(fv.field_name)
    counts[table] = (counts[table] ?? 0) + 1
  }
  return counts
}
