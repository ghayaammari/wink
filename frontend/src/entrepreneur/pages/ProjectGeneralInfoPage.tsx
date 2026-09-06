import { useState } from "react"
import { useOutletContext } from "react-router-dom"
import Field from "../../shared/components/Field"
import Modal from "../../shared/components/Modal"
import SectionCard from "../../shared/components/SectionCard"
import { useAuth } from "../../shared/context/AuthContext"
import type { ExtractedFieldSpec } from "../components/ExtractedFieldsReview"
import DetectedFieldsModal from "../components/DetectedFieldsModal"
import UpdateProjectForm from "../components/UpdateProjectForm"
import { currentValueLabel } from "../utils/projectFieldCurrentValue"
import { STAGE_LABELS } from "../utils/projectStageOptions"
import type { MyProjectOutletContext } from "./MyProjectLayout"

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

/** Un champ jamais renseigné ET sans candidate détectée n'a rien à afficher :
 * ni label, ni tiret. Une candidate en attente se règle uniquement via le
 * popup "Consulter les informations détectées" (voir DetectedFieldsModal) —
 * plus de résolution inline champ par champ sur cette page. */
function isEmptyField(project: MyProjectOutletContext["project"], fieldName: string, hasCandidate: boolean): boolean {
  return currentValueLabel(project, fieldName) === "—" && !hasCandidate
}

/**
 * "Mon Projet" → Informations générales (table `projects`). Lecture seule :
 * la seule action de résolution possible est "Consulter les informations
 * détectées" (toutes les candidates en attente, y compris project_type/stage,
 * dans un unique popup — voir DetectedFieldsModal.tsx) et "Mettre à jour"
 * (édition directe des colonnes, voir UpdateProjectForm.tsx). Les 2 chemins
 * écrivent sur les mêmes colonnes via le même backend validé, donc pas de
 * risque d'incohérence entre eux.
 *
 * `project`/`fieldValues` viennent de MyProjectLayout (route parente) : plus
 * de fetch ni de guard loading/erreur ici, déjà gérés une seule fois en amont.
 */
export default function ProjectGeneralInfoPage() {
  const { accessToken } = useAuth()
  const { project, fieldValues, refresh } = useOutletContext<MyProjectOutletContext>()
  const scopedFieldValues = fieldValues.filter((v) => v.field_name.startsWith("projects."))
  const pendingCount = scopedFieldValues.filter((v) => v.validation_status === "en_attente").length

  const [isUpdateModalOpen, setIsUpdateModalOpen] = useState(false)
  const [isDetectedModalOpen, setIsDetectedModalOpen] = useState(false)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Informations générales</h1>
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
        <Modal title="Mettre à jour le projet" onClose={() => setIsUpdateModalOpen(false)}>
          <UpdateProjectForm
            project={project}
            accessToken={accessToken!}
            onCancel={() => setIsUpdateModalOpen(false)}
            onSaved={() => {
              setIsUpdateModalOpen(false)
              refresh()
            }}
          />
        </Modal>
      )}

      {isDetectedModalOpen && (
        <Modal title="Informations détectées" onClose={() => setIsDetectedModalOpen(false)}>
          <DetectedFieldsModal
            project={project}
            fields={FIELDS}
            fieldValues={scopedFieldValues}
            accessToken={accessToken!}
            onClose={() => setIsDetectedModalOpen(false)}
            onSaved={() => {
              setIsDetectedModalOpen(false)
              refresh()
            }}
          />
        </Modal>
      )}

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
          {FIELDS.map((spec) => {
            const hasCandidate = scopedFieldValues.some(
              (v) => v.field_name === spec.fieldName && v.validation_status === "en_attente",
            )
            if (isEmptyField(project, spec.fieldName, hasCandidate)) return null

            const value = currentValueLabel(project, spec.fieldName)
            return (
              <div key={spec.fieldName} className="flex flex-col gap-1.5">
                {value !== "—" && <Field label={spec.label} value={value} />}
              </div>
            )
          })}
        </div>
      </SectionCard>
    </div>
  )
}
