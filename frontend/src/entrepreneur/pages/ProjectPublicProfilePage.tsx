import { useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import Field from "../../shared/components/Field"
import Modal from "../../shared/components/Modal"
import SectionCard from "../../shared/components/SectionCard"
import { useAuth } from "../../shared/context/AuthContext"
import { getPublicProfile, type ProjectPublicProfileRead } from "../api/projectApi"
import type { ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import SimpleDetectedFieldsModal from "../components/SimpleDetectedFieldsModal"
import UpdatePublicProfileForm from "../components/UpdatePublicProfileForm"
import { VISIBILITY_OPTIONS, visibilityLabel } from "../utils/projectVisibilityOptions"
import type { MyProjectOutletContext } from "./MyProjectLayout"

// logo_url volontairement absent : jamais extrait d'un document texte (voir
// document_service.py) — pas de candidate possible pour ce champ, uniquement
// l'upload manuel (écran 9 de l'onboarding).
// funding_visibility/compliance_visibility : `options` fait afficher un <select>
// (pas de texte libre) dans le popup "Consulter les informations détectées" —
// voir SimpleDetectedFieldsModal.tsx et le CheckConstraint ajouté en base.
const FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "project_public_profiles.public_name", label: "Nom public", kind: "text" },
  { fieldName: "project_public_profiles.public_summary", label: "Résumé public", kind: "text" },
  { fieldName: "project_public_profiles.sector", label: "Secteur (vitrine)", kind: "text" },
  { fieldName: "project_public_profiles.technologies", label: "Technologies (vitrine)", kind: "list" },
  { fieldName: "project_public_profiles.website_url", label: "Site web", kind: "text" },
  {
    fieldName: "project_public_profiles.funding_visibility",
    label: "Visibilité — levée de fonds",
    kind: "text",
    options: VISIBILITY_OPTIONS,
  },
  {
    fieldName: "project_public_profiles.compliance_visibility",
    label: "Visibilité — conformité",
    kind: "text",
    options: VISIBILITY_OPTIONS,
  },
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
      return visibilityLabel(publicProfile.funding_visibility)
    case "project_public_profiles.compliance_visibility":
      return visibilityLabel(publicProfile.compliance_visibility)
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
 * Résolution des candidates uniquement via le popup "Consulter les informations
 * détectées" (SimpleDetectedFieldsModal, même mécanisme que "Informations
 * générales"/"Informations légales") — plus de résolution inline champ par
 * champ sur cette page (ExtractedFieldsReview retiré).
 *
 * "Mettre à jour" ouvre un formulaire pré-rempli (voir UpdatePublicProfileForm) qui
 * réutilise `upsertPublicProfile` (POST déjà upsert côté backend) — aucun
 * changement backend nécessaire ici, contrairement à "Informations légales".
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
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false)
  const [isDetectedModalOpen, setIsDetectedModalOpen] = useState(false)

  function reloadPublicProfile() {
    if (accessToken) getPublicProfile(accessToken, project.id).then(setPublicProfile)
  }

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
  const pendingCount = scopedFieldValues.filter((v) => v.validation_status === "en_attente").length

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Vitrine publique</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setIsDetectedModalOpen(true)}
            className="relative rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
          >
            Consulter les informations détectées
            {pendingCount > 0 && (
              <span className="ml-2 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1.5 text-xs font-semibold text-white">
                {pendingCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setIsUpdateModalOpen(true)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
          >
            Mettre à jour
          </button>
        </div>
      </div>

      {isUpdateModalOpen && (
        <Modal title="Mettre à jour la vitrine publique" onClose={() => setIsUpdateModalOpen(false)}>
          <UpdatePublicProfileForm
            projectId={project.id}
            publicProfile={publicProfile}
            accessToken={accessToken!}
            onCancel={() => setIsUpdateModalOpen(false)}
            onSaved={() => {
              setIsUpdateModalOpen(false)
              reloadPublicProfile()
              refresh()
            }}
          />
        </Modal>
      )}

      {isDetectedModalOpen && (
        <Modal title="Informations détectées" onClose={() => setIsDetectedModalOpen(false)}>
          <SimpleDetectedFieldsModal
            fields={FIELDS}
            fieldValues={scopedFieldValues}
            currentValueLabel={(fieldName) => displayValue(publicProfile, fieldName)}
            projectId={project.id}
            accessToken={accessToken!}
            onClose={() => setIsDetectedModalOpen(false)}
            onSaved={() => {
              setIsDetectedModalOpen(false)
              reloadPublicProfile()
              refresh()
            }}
          />
        </Modal>
      )}

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
          {FIELDS.map((spec) => {
            const value = displayValue(publicProfile, spec.fieldName)
            if (value === "—") return null
            return <Field key={spec.fieldName} label={spec.label} value={value} />
          })}
        </div>
      </SectionCard>
    </div>
  )
}
