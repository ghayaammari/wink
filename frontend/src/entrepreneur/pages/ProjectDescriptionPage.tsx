import { type ChangeEvent, type FormEvent, useRef, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { updateProject, uploadDocument } from "../api/projectApi"
import { ExtractedFieldFrame } from "../components/ExtractedFieldFrame"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"
import { useDraftSync } from "../hooks/useDraftSync"
import { useExtractedFieldTracking } from "../hooks/useExtractedFieldTracking"
import { extractedText } from "../utils/extractedFieldValue"
import { clearDraft, readDraft } from "../utils/formDraft"

type Step = "choix" | "texte_libre" | "document_upload"

const FIELD_DESCRIPTION = "projects.description"

interface Draft {
  description: string
}

/** Écran 4 — service 0.0.2 : deux chemins possibles pour répondre à la
 * description du projet — texte libre (Chemin A, comportement historique) ou
 * import de document (Chemin B, extraction automatique). Voir "Wink —
 * Scénario onboarding avec import de document" (Notion) pour le détail des
 * deux chemins.
 *
 * Pas d'écran de confirmation séparé (`document_confirm`, ancienne version) :
 * après upload, la description extraite préremplit directement le textarea de
 * saisie manuelle (pattern inline, voir `ExtractedFieldFrame`) — un seul appel
 * PATCH au clic sur "Continuer", jamais un appel par champ (voir DECISIONS
 * "confirmation globale").
 */
export default function ProjectDescriptionPage() {
  const {
    project,
    setProject,
    fieldValues,
    setFieldValues,
    goNext,
    goPrevious,
  } = useOnboardingWizard()
  const { accessToken } = useAuth()

  const tracking = useExtractedFieldTracking(fieldValues, [FIELD_DESCRIPTION])
  const draft = project ? readDraft<Draft>(project.id, "description") : null

  const [step, setStep] = useState<Step>("choix")
  const [description, setDescription] = useState(
    draft?.description ?? project?.description ?? "",
  )
  const [documentFile, setDocumentFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useDraftSync(project?.id, "description", { description }, !isSubmitting)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setDocumentFile(event.target.files?.[0] ?? null)
  }

  async function handleUpload() {
    if (!accessToken || !project || !documentFile) return

    setError(null)
    setIsSubmitting(true)
    try {
      const values = await uploadDocument(accessToken, project.id, documentFile)
      setFieldValues(values)

      // Contrairement aux écrans 5-9 (qui montent APRÈS que fieldValues soit
      // déjà peuplé, l'upload ayant eu lieu sur un écran précédent), ce
      // composant est déjà monté au moment de l'upload — le useState initial
      // du textarea n'a pas pu voir la valeur extraite tout seul. On la pousse
      // donc explicitement ici, au moment de basculer vers "texte_libre".
      const descriptionField = values.find(
        (v) => v.field_name === FIELD_DESCRIPTION,
      )
      if (descriptionField) {
        setDescription(extractedText(descriptionField.field_value))
      }
      setStep("texte_libre")
    } catch (err) {
      // Le document peut avoir été importé même si cette erreur est levée
      // (échec de l'extraction seulement, voir document_service.py) — on ne
      // bloque pas l'utilisateur, il peut continuer en texte libre.
      setError(
        err instanceof ApiError ? err.message : "Une erreur est survenue.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleSubmitFreeText(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      const updated = await updateProject(accessToken, project.id, {
        description,
        resolved_field_values: tracking.buildResolutions(),
      })
      setProject(updated)
      clearDraft(project.id, "description")
      goNext()
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Une erreur est survenue.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  if (step === "choix") {
    return (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-500">
          Comment veux-tu décrire ton projet ?
        </p>
        <button
          type="button"
          onClick={() => setStep("texte_libre")}
          className="rounded-lg border border-gray-300 px-4 py-3 text-left text-sm font-medium text-gray-900 hover:border-indigo-400 hover:bg-indigo-50/50"
        >
          Décrire mon projet moi-même
        </button>
        <button
          type="button"
          onClick={() => setStep("document_upload")}
          className="rounded-lg border border-gray-300 px-4 py-3 text-left text-sm font-medium text-gray-900 hover:border-indigo-400 hover:bg-indigo-50/50"
        >
          Importer un document (pitch deck, executive summary...)
        </button>

        <div className="flex justify-start">
          <button
            type="button"
            onClick={goPrevious}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            Précédent
          </button>
        </div>
      </div>
    )
  }

  if (step === "document_upload") {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Document (PDF uniquement)
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={handleFileChange}
            className="hidden"
            id="project-document-upload"
          />
          <label
            htmlFor="project-document-upload"
            className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-gray-300 px-4 py-8 text-center transition hover:border-indigo-400 hover:bg-indigo-50/50"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="h-8 w-8 text-gray-400"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8.25 12 3.75m0 0L7.5 8.25M12 3.75v13.5"
              />
            </svg>
            <span className="text-sm font-medium text-gray-700">
              {documentFile
                ? documentFile.name
                : "Cliquer pour importer ton document"}
            </span>
            <span className="text-xs text-gray-400">
              PDF — pitch deck, executive summary...
            </span>
          </label>
        </div>

        {error && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-red-600">{error}</p>
            <button
              type="button"
              onClick={() => setStep("texte_libre")}
              className="text-left text-sm text-indigo-600 hover:underline"
            >
              Continuer en texte libre à la place
            </button>
          </div>
        )}

        <div className="flex justify-between">
          <button
            type="button"
            onClick={() => setStep("choix")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            Précédent
          </button>
          <button
            type="button"
            onClick={handleUpload}
            disabled={!documentFile || isSubmitting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Analyse en cours..." : "Importer et analyser"}
          </button>
        </div>
      </div>
    )
  }

  // step === "texte_libre"
  return (
    <form onSubmit={handleSubmitFreeText} className="flex flex-col gap-4">
      <ExtractedFieldFrame
        active={tracking.isActive(FIELD_DESCRIPTION)}
        touched={tracking.isTouched(FIELD_DESCRIPTION)}
        onIgnore={() => {
          tracking.ignore(FIELD_DESCRIPTION)
          setDescription("")
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Décris ton idée ou ta startup en quelques phrases
          </label>
          <textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value)
              tracking.markTouched(FIELD_DESCRIPTION)
            }}
            required
            minLength={1}
            rows={6}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            placeholder="Qu'est-ce que vous faites, pour qui, et pourquoi maintenant ?"
          />
        </div>
      </ExtractedFieldFrame>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-between">
        <button
          type="button"
          onClick={() => setStep("choix")}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          Précédent
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Continuer"}
        </button>
      </div>
    </form>
  )
}
