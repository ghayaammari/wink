import { useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { useAuth } from "../../shared/context/AuthContext"
import Field from "../../shared/components/Field"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import Modal from "../../shared/components/Modal"
import SectionCard from "../../shared/components/SectionCard"
import { getLegalProfile, type ProjectFieldValueRead, type ProjectLegalProfileRead } from "../api/projectApi"
import type { ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import SimpleDetectedFieldsModal from "../components/SimpleDetectedFieldsModal"
import UpdateLegalProfileForm from "../components/UpdateLegalProfileForm"
import VerificationStatusBadge from "../components/VerificationStatusBadge"
import type { MyProjectOutletContext } from "./MyProjectLayout"

// legal_name/legal_form ne dépendent pas de l'immatriculation officielle — on peut
// choisir un nom et une forme juridique avant d'être créée (voir DECISIONS) : ces 2
// champs restent donc éditables quel que soit `project_type`.
const IDENTITY_FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "project_legal_profiles.legal_name", label: "Nom légal", kind: "text" },
  { fieldName: "project_legal_profiles.legal_form", label: "Forme juridique", kind: "text" },
]

// Ces champs n'existent pas tant que la société n'est pas réellement immatriculée
// (pas de SIREN/SIRET avant ça) — affichés uniquement quand `project_type === "created"`.
const REGISTRATION_FIELDS: ExtractedFieldSpec[] = [
  { fieldName: "project_legal_profiles.registration_number", label: "Numéro d'immatriculation", kind: "text" },
  { fieldName: "project_legal_profiles.siren", label: "SIREN", kind: "text" },
  { fieldName: "project_legal_profiles.siret", label: "SIRET", kind: "text" },
  { fieldName: "project_legal_profiles.vat_number", label: "N° TVA", kind: "text" },
  { fieldName: "project_legal_profiles.naf_code", label: "Code NAF", kind: "text" },
  { fieldName: "project_legal_profiles.registration_date", label: "Date d'immatriculation", kind: "text" },
]

// registered_address / legal_representative volontairement exclus : ce sont des
// objets JSON (voir project_legal_profile.py), pas gérés par les types
// text/number/list/boolean de SimpleDetectedFieldsModal. Une candidate pour ces 2
// champs reste donc en_attente, invisible ici — limitation connue à lever dans
// un futur incrément plutôt que de bricoler un type JSON juste pour ces 2 champs.

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

/** true s'il existe au moins une candidate en attente sur un des champs
 * d'immatriculation (SIREN/SIRET/...) alors que la section est encore
 * verrouillée (`project_type !== "created"`). On n'affiche PAS la valeur elle-
 * même ici — juste le fait qu'il y en a une — pour ne pas laisser croire qu'un
 * SIRET/SIREN est "confirmé" avant que la société soit réellement immatriculée.
 * L'info n'est pas perdue pour autant : la candidate reste en base (`en_attente`)
 * et redevient normalement résolvable (avec sa valeur, dans le popup) dès que
 * `project_type` passe à "created". */
function hasPendingRegistrationCandidate(fieldValues: ProjectFieldValueRead[]): boolean {
  return REGISTRATION_FIELDS.some((spec) =>
    fieldValues.some((fv) => fv.field_name === spec.fieldName && fv.validation_status === "en_attente"),
  )
}

/**
 * "Mon Projet" → Informations légales (table `project_legal_profiles`).
 *
 * `legal_name`/`legal_form` restent éditables quel que soit `project_type` (voir
 * IDENTITY_FIELDS) ; les champs d'immatriculation (SIREN/SIRET/...) restent
 * masqués tant que `project_type !== "created"` — un message générique signale
 * qu'une candidate existe sans en révéler la valeur (voir
 * hasPendingRegistrationCandidate), jamais silencieusement ignorée.
 *
 * Résolution des candidates uniquement via le popup "Consulter les informations
 * détectées" (SimpleDetectedFieldsModal, même mécanisme que "Informations
 * générales" mais sans project_type/stage) — plus de résolution inline champ
 * par champ sur cette page (ExtractedFieldsReview retiré).
 *
 * "Mettre à jour" ouvre un formulaire pré-rempli (voir UpdateLegalProfileForm) qui
 * PATCH /projects/{id}/legal-profile — route ajoutée pour cet écran, `create_legal_profile`
 * (POST) échouant si un profil existe déjà.
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente). Seul
 * `legalProfile` reste propre à cette page : ce n'est pas une donnée partagée
 * par les 3 sections, pas de raison de la faire porter par le layout commun.
 */
export default function ProjectLegalInfoPage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const [legalProfile, setLegalProfile] = useState<ProjectLegalProfileRead | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false)
  const [isDetectedModalOpen, setIsDetectedModalOpen] = useState(false)
  const isCreated = project.project_type === "created"

  function reloadLegalProfile() {
    if (accessToken) getLegalProfile(accessToken, project.id).then(setLegalProfile)
  }

  // Un seul point de fermeture pour la modale "Mettre à jour" — utilisé à la
  // fois par le "×" natif de Modal et par le bouton interne du formulaire
  // (voir UpdateLegalProfileForm.tsx). Rafraîchit systématiquement, même si
  // rien n'a été modifié : bug réel corrigé ici — le "×" fermait la modale
  // sans jamais recharger le profil, donc la page affichait encore les
  // anciennes valeurs après une mise à jour tant qu'on ne rechargeait pas la
  // page entière à la main.
  function closeUpdateModal() {
    setIsUpdateModalOpen(false)
    reloadLegalProfile()
    refresh()
  }

  useEffect(() => {
    if (!accessToken) return
    setIsLoading(true)
    getLegalProfile(accessToken, project.id)
      .then(setLegalProfile)
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage et si le projet change
  }, [accessToken, project.id])

  if (isLoading) return <LoadingSpinner />

  const scopedFieldValues = fieldValues.filter((v) => v.field_name.startsWith("project_legal_profiles."))
  // Champs réellement proposables dans le popup en ce moment — l'immatriculation
  // reste exclue tant que la section est verrouillée (même règle que l'affichage),
  // pour ne pas compter/montrer une candidate qu'on ne veut pas encore révéler.
  const modalFields = isCreated ? [...IDENTITY_FIELDS, ...REGISTRATION_FIELDS] : IDENTITY_FIELDS
  const pendingCount = scopedFieldValues.filter(
    (v) =>
      v.validation_status === "en_attente" &&
      modalFields.some((spec) => spec.fieldName === v.field_name),
  ).length

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Informations légales</h1>
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
        <Modal title="Mettre à jour les informations légales" onClose={closeUpdateModal}>
          <UpdateLegalProfileForm
            projectId={project.id}
            legalProfile={legalProfile}
            isCreated={isCreated}
            accessToken={accessToken!}
            onClose={closeUpdateModal}
          />
        </Modal>
      )}

      {isDetectedModalOpen && (
        <Modal title="Informations détectées" onClose={() => setIsDetectedModalOpen(false)}>
          <SimpleDetectedFieldsModal
            fields={modalFields}
            fieldValues={scopedFieldValues}
            currentValueLabel={(fieldName) => displayValue(legalProfile, fieldName)}
            projectId={project.id}
            accessToken={accessToken!}
            onClose={() => setIsDetectedModalOpen(false)}
            onSaved={() => {
              setIsDetectedModalOpen(false)
              reloadLegalProfile()
              refresh()
            }}
          />
        </Modal>
      )}

      <SectionCard title="Identité légale">
        <div className="flex flex-col gap-4">
          {IDENTITY_FIELDS.map((spec) => {
            const value = displayValue(legalProfile, spec.fieldName)
            if (value === "—") return null
            return <Field key={spec.fieldName} label={spec.label} value={value} />
          })}
        </div>
      </SectionCard>

      {isCreated ? (
        <SectionCard title="Immatriculation">
          <div className="flex flex-col gap-4">
            {legalProfile?.siren && (
              // Affichage permanent des 3 statuts — mis à jour uniquement au clic
              // sur "Mettre à jour" (voir UpdateLegalProfileForm.tsx), jamais par
              // un appel automatique ici : cet écran reste une simple lecture.
              <div className="flex flex-wrap items-center gap-4 rounded-lg bg-gray-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Dénomination</span>
                  <VerificationStatusBadge status={legalProfile.denomination_verification_status} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">SIREN / SIRET</span>
                  <VerificationStatusBadge status={legalProfile.immatriculation_verification_status} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Kbis</span>
                  <VerificationStatusBadge status={legalProfile.kbis_verification_status} />
                </div>
              </div>
            )}
            {REGISTRATION_FIELDS.map((spec) => {
              const value = displayValue(legalProfile, spec.fieldName)
              if (value === "—") return null
              return <Field key={spec.fieldName} label={spec.label} value={value} />
            })}
          </div>
        </SectionCard>
      ) : (
        <SectionCard title="Immatriculation">
          <p className="text-sm text-gray-500">
            Cette section s'active une fois ta société immatriculée .
          </p>
          {hasPendingRegistrationCandidate(scopedFieldValues) && (
            <p className="mt-3 text-xs text-gray-500">
              🔎 Des informations d'immatriculation ont été détectées dans un document
              déposé — elles seront à valider une fois ta société immatriculée.
            </p>
          )}
        </SectionCard>
      )}
    </div>
  )
}
