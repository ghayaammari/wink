import { type FormEvent, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { createLegalProfile } from "../api/projectApi"
import { useOnboardingWizard } from "../context/OnboardingWizardContext"

const LEGAL_FORM_OPTIONS = ["SAS", "SASU", "SARL", "EURL", "SA", "SNC", "Société civile", "Autre"]

/** Écran 3 — uniquement affiché si project_type = "created" (voir `steps` dans
 * OnboardingWizardContext). Le questionnaire d'origine ne demandait que
 * legal_name + siren ; `legal_form` ajouté à la demande, la colonne existe déjà
 * sur `project_legal_profiles` (pas de changement backend nécessaire). Le reste
 * du profil légal (siret, adresse...) sera complété dans un futur incrément. */
export default function LegalProfilePage() {
  const [legalName, setLegalName] = useState("")
  const [legalForm, setLegalForm] = useState("")
  const [siren, setSiren] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { accessToken } = useAuth()
  const { project, goNext, goPrevious } = useOnboardingWizard()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !project) return

    setError(null)
    setIsSubmitting(true)
    try {
      await createLegalProfile(accessToken, project.id, {
        is_registered: true,
        legal_name: legalName || undefined,
        legal_form: legalForm || undefined,
        siren: siren || undefined,
      })
      goNext()
    } catch (err) {
      // Reprise du wizard après un rechargement de page : le profil légal a pu
      // être créé lors d'un passage précédent sur cet écran. create_legal_profile
      // refuse un doublon (ProjectError), ce qui n'est pas une vraie erreur ici —
      // on avance simplement plutôt que de bloquer l'utilisateur.
      if (err instanceof ApiError && err.status === 400) {
        goNext()
        return
      }
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Nom légal de la société</label>
        <input
          type="text"
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
          placeholder="Ex: Wink SAS"
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Forme juridique</label>
        <select
          value={legalForm}
          onChange={(e) => setLegalForm(e.target.value)}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        >
          <option value="">Sélectionner...</option>
          {LEGAL_FORM_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">SIREN</label>
        <input
          type="text"
          value={siren}
          onChange={(e) => setSiren(e.target.value)}
          placeholder="9 chiffres"
          pattern="\d{9}"
          maxLength={9}
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-between">
        <button
          type="button"
          onClick={goPrevious}
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
