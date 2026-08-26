import { useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import Field from "../../shared/components/Field"
import SectionCard from "../../shared/components/SectionCard"
import { useAuth } from "../../shared/context/AuthContext"
import { getPublicProfile, type ProjectPublicProfileRead } from "../api/projectApi"
import ExtractedFieldsReview, { type ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import type { MyProjectOutletContext } from "./MyProjectLayout"

// logo_url volontairement absent : jamais extrait d'un document texte (voir
// document_service.py) — pas de candidate possible pour ce champ, uniquement
// l'upload manuel (écran 9 de l'onboarding).
const FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "project_public_profiles.public_name", label: "Nom public", kind: "text" },
  { fieldName: "project_public_profiles.public_summary", label: "Résumé public", kind: "text" },
  { fieldName: "project_public_profiles.sector", label: "Secteur (vitrine)", kind: "text" },
  { fieldName: "project_public_profiles.technologies", label: "Technologies (vitrine)", kind: "list" },
  { fieldName: "project_public_profiles.website_url", label: "Site web", kind: "text" },
  { fieldName: "project_public_profiles.funding_visibility", label: "Visibilité — levée de fonds", kind: "text" },
  { fieldName: "project_public_profiles.compliance_visibility", label: "Visibilité — conformité", kind: "text" },
]

function listOrDash(items: string[]): string {
  return items.length > 0 ? items.join(", ") : "—"
}

function displayValue(publicProfile: ProjectPublicProfileRead | null, fieldName: string): string {
  if (!publicProfile) return "—"
  switch (fieldName) {
    case "project_public_profiles.public_name":
      return publicProfile.public_name ?? "—"
    case "project_public_profiles.public_summary":
      return publicProfile.public_summary ?? "—"
    case "project_public_profiles.sector":
      return publicProfile.sector ?? "—"
    case "project_public_profiles.technologies":
      return listOrDash(publicProfile.technologies)
    case "project_public_profiles.website_url":
      return publicProfile.website_url ?? "—"
    case "project_public_profiles.funding_visibility":
      return publicProfile.funding_visibility
    case "project_public_profiles.compliance_visibility":
      return publicProfile.compliance_visibility
    default:
      return "—"
  }
}

/**
 * "Mon Projet" → Vitrine publique (table `project_public_profiles`). Toujours
 * accessible, contrairement à "Informations légales" — la vitrine publique
 * est facultative dans le questionnaire (bouton "Passer" à l'écran 9) mais
 * jamais conditionnée à `project_type`.
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente). Seul
 * `publicProfile` reste propre à cette page (même raisonnement que
 * `legalProfile` dans ProjectLegalInfoPage.tsx).
 */
export default function ProjectPublicProfilePage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const [publicProfile, setPublicProfile] = useState<ProjectPublicProfileRead | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!accessToken) return
    setIsLoading(true)
    getPublicProfile(accessToken, project.id)
      .then(setPublicProfile)
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage et si le projet change
  }, [accessToken, project.id])

  if (isLoading) return <p className="text-sm text-gray-500">Chargement...</p>

  const scopedFieldValues = fieldValues.filter((v) => v.field_name.startsWith("project_public_profiles."))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Vitrine publique</h1>
        <button
          type="button"
          disabled
          title="Bientôt disponible"
          className="cursor-not-allowed rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-400"
        >
          Mettre à jour
        </button>
      </div>

      <SectionCard title="Logo">
        {publicProfile?.logo_url ? (
          <img
            src={publicProfile.logo_url}
            alt="Logo du projet"
            className="h-14 w-14 rounded-lg object-cover"
          />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-gray-100 text-xs text-gray-400">
            Logo
          </div>
        )}
      </SectionCard>

      <SectionCard title="Présentation publique">
        <div className="flex flex-col gap-4">
          {FIELDS.map((spec) => (
            <div key={spec.fieldName} className="flex flex-col gap-1.5">
              <Field label={spec.label} value={displayValue(publicProfile, spec.fieldName)} />
              <ExtractedFieldsReview
                fields={[spec]}
                fieldValues={scopedFieldValues}
                projectId={project.id}
                accessToken={accessToken!}
                compact
                onFieldValuesChange={() => {
                  refresh()
                  if (accessToken) getPublicProfile(accessToken, project.id).then(setPublicProfile)
                }}
              />
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  )
}
