/**
 * Règles de cohérence `project_type` ↔ `stage`, partagées entre
 * ProjectGeneralInfoPage.tsx (FieldConflictReview) et UpdateProjectForm.tsx —
 * une seule définition pour éviter que les deux endroits divergent (c'est
 * exactement le bug qu'on a eu avec le comptage des badges avant).
 *
 * Même règle que l'écran 2 de l'onboarding (ProjectStagePage.tsx), précisée ici :
 * - "Pas encore créée" → Idéation, Pré-amorçage
 * - "Déjà créée" → Pré-amorçage, Amorçage, Série A
 */

export interface StageOption {
  value: string
  label: string
}

export const STAGE_LABELS: Record<string, string> = {
  ideation: "Idéation",
  pre_seed: "Pré-amorçage",
  seed: "Amorçage",
  serie_a: "Série A",
}

export const PROJECT_TYPE_OPTIONS: StageOption[] = [
  { value: "not_created", label: "Pas encore créée" },
  { value: "created", label: "Déjà créée" },
]

export const STAGE_OPTIONS: StageOption[] = Object.entries(STAGE_LABELS).map(([value, label]) => ({
  value,
  label,
}))

const NOT_CREATED_STAGES = new Set(["ideation", "pre_seed"])
const CREATED_STAGES = new Set(["pre_seed", "seed", "serie_a"])

export function stageOptionsFor(projectType: string): StageOption[] {
  const allowed = projectType === "not_created" ? NOT_CREATED_STAGES : CREATED_STAGES
  return STAGE_OPTIONS.filter((o) => allowed.has(o.value))
}

export function isStageValidFor(projectType: string, stage: string): boolean {
  return stageOptionsFor(projectType).some((o) => o.value === stage)
}
