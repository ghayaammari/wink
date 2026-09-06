/**
 * Valeur "actuelle" (déjà en base, table `projects`) d'un champ identifié par
 * son `field_name` préfixé ("projects.sector", ...) — partagé entre
 * ProjectGeneralInfoPage.tsx (affichage en lecture seule) et
 * DetectedFieldsModal.tsx ("Actuel" affiché à côté de "Détecté"), pour éviter
 * que les deux gardent chacun leur propre switch/case et divergent.
 */
import type { ProjectRead } from "../api/projectApi"
import { STAGE_LABELS } from "./projectStageOptions"

function listOrDash(items: string[]): string {
  return items.length > 0 ? items.join(", ") : "—"
}

export function currentValueLabel(project: ProjectRead, fieldName: string): string {
  switch (fieldName) {
    case "projects.project_type":
      return project.project_type === "created" ? "Déjà créée" : "Pas encore créée"
    case "projects.stage":
      return STAGE_LABELS[project.stage]
    case "projects.description":
      return project.description ?? "—"
    case "projects.sector":
      return project.sector ?? "—"
    case "projects.subsectors":
      return listOrDash(project.subsectors)
    case "projects.customer_segments":
      return listOrDash(project.customer_segments)
    case "projects.target_users":
      return listOrDash(project.target_users)
    case "projects.nombre_cofondateurs":
      return project.nombre_cofondateurs?.toString() ?? "—"
    case "projects.intention_levee_fonds":
      return project.intention_levee_fonds === null
        ? "Pas encore décidé"
        : project.intention_levee_fonds
          ? "Oui"
          : "Non"
    case "projects.technologies":
      return listOrDash(project.technologies)
    case "projects.value_proposition":
      return project.value_proposition ?? "—"
    case "projects.localisation":
      return project.localisation ?? "—"
    default:
      return "—"
  }
}
