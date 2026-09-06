/**
 * Valeurs acceptées pour `project_public_profiles.funding_visibility` /
 * `.compliance_visibility` — reflète le CheckConstraint ajouté en base (voir
 * migration `82a64157b35d_add_visibility_check_project_public_profiles`) et le
 * type `ProjectVisibility` côté backend (project_public_profile_schemas.py).
 * Seule source de vérité partagée entre UpdatePublicProfileForm.tsx et
 * ProjectPublicProfilePage.tsx (affichage), même raisonnement que
 * projectStageOptions.ts pour project_type/stage.
 */

export interface VisibilityOption {
  value: string
  label: string
}

export const VISIBILITY_OPTIONS: VisibilityOption[] = [
  { value: "private", label: "Privée" },
  { value: "public", label: "Publique" },
  { value: "investors_only", label: "Investisseurs uniquement" },
]

export function visibilityLabel(value: string): string {
  return VISIBILITY_OPTIONS.find((o) => o.value === value)?.label ?? value
}
