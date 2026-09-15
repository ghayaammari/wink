/**
 * Codes d'objectifs immédiats (`projects.objectifs_immediats`), partagés entre
 * l'écran 6 de l'onboarding (TeamFundingPage.tsx) et le formulaire "Mettre à jour"
 * du profil (UpdateProjectForm.tsx) — une seule source pour éviter que les deux
 * endroits divergent sur les codes proposés à l'utilisateur.
 *
 * Seuls les codes connus du moteur de filtrage de la roadmap (service 1.1.11,
 * condition e23_depot_marque) sont proposés. Un code ajouté côté JSON seed doit
 * être ajouté ici (et dans `_apply_condition` du roadmap_service.py).
 * (réalisé par OPENCODE)
 */

export const OBJECTIF_PROTECTION_MARQUE = "protection_marque_code"

export interface ImmediateObjectiveOption {
  value: string
  label: string
}

export const IMMEDIATE_OBJECTIVES: ImmediateObjectiveOption[] = [
  {
    value: OBJECTIF_PROTECTION_MARQUE,
    label: "Protéger mon nom ou mon logo (dépôt de marque)",
  },
]

/** Codes → libellés lisibles (passent les codes inconnus tels quels). */
export function immediateObjectiveLabels(codes: string[]): string[] {
  return codes.map((code) => IMMEDIATE_OBJECTIVES.find((o) => o.value === code)?.label ?? code)
}