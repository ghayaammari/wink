import { useOutletContext } from "react-router-dom"
import Field from "../../shared/components/Field"
import SectionCard from "../../shared/components/SectionCard"
import { useAuth } from "../../shared/context/AuthContext"
import type { ProjectRead } from "../api/projectApi"
import ExtractedFieldsReview, { type ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import type { MyProjectOutletContext } from "./MyProjectLayout"

const STAGE_LABELS: Record<ProjectRead["stage"], string> = {
  ideation: "Idéation",
  pre_seed: "Pré-amorçage",
  seed: "Amorçage",
  serie_a: "Série A",
}

const FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "projects.description", label: "Description", kind: "text" },
  { fieldName: "projects.sector", label: "Secteur", kind: "text" },
  { fieldName: "projects.subsectors", label: "Sous-secteurs", kind: "list" },
  { fieldName: "projects.customer_segments", label: "Segments clients", kind: "list" },
  { fieldName: "projects.target_users", label: "Utilisateurs cibles", kind: "list" },
  { fieldName: "projects.nombre_cofondateurs", label: "Cofondateurs", kind: "number" },
  { fieldName: "projects.intention_levee_fonds", label: "Intention de levée de fonds", kind: "boolean" },
  { fieldName: "projects.technologies", label: "Technologies", kind: "list" },
  { fieldName: "projects.value_proposition", label: "Proposition de valeur", kind: "text" },
  { fieldName: "projects.localisation", label: "Localisation", kind: "text" },
]

function listOrDash(items: string[]): string {
  return items.length > 0 ? items.join(", ") : "—"
}

/** Valeur affichée pour un champ SANS candidate en attente — lecture seule,
 * lue directement sur `project` (voir DECISIONS : pas d'édition générale sur
 * cette page pour I0, seule la résolution des candidates est possible). */
function displayValue(project: ProjectRead, fieldName: string): string {
  switch (fieldName) {
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

/**
 * "Mon Projet" → Informations générales (table `projects`). Un champ sans
 * candidate en attente reste en lecture seule ; un champ avec candidate
 * affiche en plus, sur la même ligne, `ExtractedFieldsReview` (Valider/
 * Modifier/Ignorer) — réutilisé champ par champ (voir ce composant) plutôt
 * qu'en bloc unique comme sur les écrans d'onboarding.
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente) : plus
 * de fetch ni de guard loading/erreur ici, déjà gérés une seule fois en amont.
 */
export default function ProjectGeneralInfoPage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const scopedFieldValues = fieldValues.filter((v) => v.field_name.startsWith("projects."))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Informations générales</h1>
        {/* Posé maintenant, branché dans un futur incrément (voir DECISIONS) —
            l'édition directe des champs sans candidate n'est pas encore possible. */}
        <button
          type="button"
          disabled
          title="Bientôt disponible"
          className="cursor-not-allowed rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-400"
        >
          Mettre à jour
        </button>
      </div>

      <SectionCard title="Stade">
        <dl className="grid grid-cols-2 gap-4">
          <Field
            label="Startup"
            value={project.project_type === "created" ? "Déjà créée" : "Pas encore créée"}
          />
          <Field label="Stade financier" value={STAGE_LABELS[project.stage]} />
        </dl>
      </SectionCard>

      <SectionCard title="Détails du projet">
        <div className="flex flex-col gap-4">
          {FIELDS.map((spec) => (
            <div key={spec.fieldName} className="flex flex-col gap-1.5">
              <Field label={spec.label} value={displayValue(project, spec.fieldName)} />
              <ExtractedFieldsReview
                fields={[spec]}
                fieldValues={scopedFieldValues}
                projectId={project.id}
                accessToken={accessToken!}
                compact
                // La résolution a écrit dans la vraie colonne `projects` — on
                // recharge pour que displayValue() reflète la nouvelle valeur.
                onFieldValuesChange={() => refresh()}
              />
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}
