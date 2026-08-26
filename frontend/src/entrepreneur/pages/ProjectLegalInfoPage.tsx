import { useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { useAuth } from "../../shared/context/AuthContext"
import Field from "../../shared/components/Field"
import SectionCard from "../../shared/components/SectionCard"
import { getLegalProfile, type ProjectLegalProfileRead } from "../api/projectApi"
import ExtractedFieldsReview, { type ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import type { MyProjectOutletContext } from "./MyProjectLayout"

// registered_address / legal_representative volontairement exclus : ce sont des
// objets JSON (voir project_legal_profile.py), pas gérés par les types
// text/number/list/boolean d'ExtractedFieldsReview. Une candidate pour ces 2
// champs reste donc en_attente, invisible ici — limitation connue à lever dans
// un futur incrément plutôt que de bricoler un type JSON juste pour ces 2 champs.
const FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "project_legal_profiles.legal_name", label: "Nom légal", kind: "text" },
  { fieldName: "project_legal_profiles.legal_form", label: "Forme juridique", kind: "text" },
  { fieldName: "project_legal_profiles.registration_number", label: "Numéro d'immatriculation", kind: "text" },
  { fieldName: "project_legal_profiles.siren", label: "SIREN", kind: "text" },
  { fieldName: "project_legal_profiles.siret", label: "SIRET", kind: "text" },
  { fieldName: "project_legal_profiles.vat_number", label: "N° TVA", kind: "text" },
  { fieldName: "project_legal_profiles.naf_code", label: "Code NAF", kind: "text" },
  { fieldName: "project_legal_profiles.registration_date", label: "Date d'immatriculation", kind: "text" },
]

function displayValue(legalProfile: ProjectLegalProfileRead | null, fieldName: string): string {
  if (!legalProfile) return "—"
  switch (fieldName) {
    case "project_legal_profiles.legal_name":
      return legalProfile.legal_name ?? "—"
    case "project_legal_profiles.legal_form":
      return legalProfile.legal_form ?? "—"
    case "project_legal_profiles.registration_number":
      return legalProfile.registration_number ?? "—"
    case "project_legal_profiles.siren":
      return legalProfile.siren ?? "—"
    case "project_legal_profiles.siret":
      return legalProfile.siret ?? "—"
    case "project_legal_profiles.vat_number":
      return legalProfile.vat_number ?? "—"
    case "project_legal_profiles.naf_code":
      return legalProfile.naf_code ?? "—"
    case "project_legal_profiles.registration_date":
      return legalProfile.registration_date ?? "—"
    default:
      return "—"
  }
}

/**
 * "Mon Projet" → Informations légales (table `project_legal_profiles`).
 *
 * Section verrouillée si `project_type = "not_created"` (même règle que
 * l'écran 3 de l'onboarding, voir LegalProfilePage.tsx) : pas de profil légal
 * possible pour une startup pas encore immatriculée. Hypothèse posée en
 * l'absence du détail exact de `Wink_page_mon_projet_variantes.md` pour cet
 * état "verrouillé" — à ajuster si ce document précise un comportement différent.
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente). Seul
 * `legalProfile` reste propre à cette page : ce n'est pas une donnée partagée
 * par les 3 sections, pas de raison de la faire porter par le layout commun.
 */
export default function ProjectLegalInfoPage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const [legalProfile, setLegalProfile] = useState<ProjectLegalProfileRead | null>(null)
  const [isLoading, setIsLoading] = useState(project.project_type === "created")

  useEffect(() => {
    if (!accessToken || project.project_type !== "created") return
    setIsLoading(true)
    getLegalProfile(accessToken, project.id)
      .then(setLegalProfile)
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage et si le projet change
  }, [accessToken, project.id, project.project_type])

  if (project.project_type !== "created") {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-xl font-semibold text-gray-900">Informations légales</h1>
        <SectionCard title="Section verrouillée">
          <p className="text-sm text-gray-500">
            Cette section s'active une fois ta société immatriculée (indiqué comme "Pas
            encore créée" à l'onboarding).
          </p>
        </SectionCard>
      </div>
    )
  }

  if (isLoading) return <p className="text-sm text-gray-500">Chargement...</p>

  const scopedFieldValues = fieldValues.filter((v) => v.field_name.startsWith("project_legal_profiles."))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Informations légales</h1>
        <button
          type="button"
          disabled
          title="Bientôt disponible"
          className="cursor-not-allowed rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-400"
        >
          Mettre à jour
        </button>
      </div>

      <SectionCard title="Identité légale">
        <div className="flex flex-col gap-4">
          {FIELDS.map((spec) => (
            <div key={spec.fieldName} className="flex flex-col gap-1.5">
              <Field label={spec.label} value={displayValue(legalProfile, spec.fieldName)} />
              <ExtractedFieldsReview
                fields={[spec]}
                fieldValues={scopedFieldValues}
                projectId={project.id}
                accessToken={accessToken!}
                compact
                onFieldValuesChange={() => {
                  refresh()
                  if (accessToken) getLegalProfile(accessToken, project.id).then(setLegalProfile)
                }}
              />
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}
