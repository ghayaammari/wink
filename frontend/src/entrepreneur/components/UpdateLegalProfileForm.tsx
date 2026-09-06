import { useState, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  updateLegalProfile,
  type ProjectLegalProfileRead,
  type ProjectLegalProfileUpdate,
} from "../api/projectApi"

interface UpdateLegalProfileFormProps {
  projectId: string
  /** `null` si l'écran 3 de l'onboarding n'a jamais été rempli — le formulaire
   * démarre alors avec des champs vides plutôt que de bloquer (voir
   * project_service.update_legal_profile, qui upsert la ligne). */
  legalProfile: ProjectLegalProfileRead | null
  /** legal_name/legal_form restent éditables même si false ; les champs
   * d'immatriculation sont masqués tant que false (même règle que l'affichage
   * en lecture seule de ProjectLegalInfoPage.tsx). */
  isCreated: boolean
  accessToken: string
  onSaved: () => void
  onCancel: () => void
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

/**
 * Formulaire du popup "Mettre à jour" (Informations légales, table
 * `project_legal_profiles`). Contrairement à UpdateProjectForm.tsx, pas de
 * champs couplés à valider — juste des champs texte, envoyés via un PATCH
 * upsert (voir updateLegalProfile).
 *
 * Les champs d'immatriculation ne sont ni affichés ni envoyés tant que
 * `isCreated` est faux : pas de risque d'écraser une candidate en_attente
 * avec une valeur vide, et cohérent avec le verrouillage déjà en place sur
 * la page (voir hasPendingRegistrationCandidate).
 */
export default function UpdateLegalProfileForm({
  projectId,
  legalProfile,
  isCreated,
  accessToken,
  onSaved,
  onCancel,
}: UpdateLegalProfileFormProps) {
  const [legalName, setLegalName] = useState(legalProfile?.legal_name ?? "")
  const [legalForm, setLegalForm] = useState(legalProfile?.legal_form ?? "")
  const [registrationNumber, setRegistrationNumber] = useState(legalProfile?.registration_number ?? "")
  const [siren, setSiren] = useState(legalProfile?.siren ?? "")
  const [siret, setSiret] = useState(legalProfile?.siret ?? "")
  const [vatNumber, setVatNumber] = useState(legalProfile?.vat_number ?? "")
  const [nafCode, setNafCode] = useState(legalProfile?.naf_code ?? "")
  const [registrationDate, setRegistrationDate] = useState(legalProfile?.registration_date ?? "")

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    const payload: ProjectLegalProfileUpdate = {
      legal_name: legalName.trim(),
      legal_form: legalForm.trim(),
      ...(isCreated
        ? {
            registration_number: registrationNumber.trim(),
            siren: siren.trim(),
            siret: siret.trim(),
            vat_number: vatNumber.trim(),
            naf_code: nafCode.trim(),
            ...(registrationDate.trim() !== "" ? { registration_date: registrationDate.trim() } : {}),
          }
        : {}),
    }

    setIsSubmitting(true)
    try {
      await updateLegalProfile(accessToken, projectId, payload)
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-legal-name">
          Nom légal
        </label>
        <input
          id="update-legal-name"
          type="text"
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-legal-form">
          Forme juridique
        </label>
        <input
          id="update-legal-form"
          type="text"
          value={legalForm}
          onChange={(e) => setLegalForm(e.target.value)}
          className={inputClass}
        />
      </div>

      {isCreated ? (
        <>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass} htmlFor="update-registration-number">
              Numéro d'immatriculation
            </label>
            <input
              id="update-registration-number"
              type="text"
              value={registrationNumber}
              onChange={(e) => setRegistrationNumber(e.target.value)}
              className={inputClass}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass} htmlFor="update-siren">
                SIREN
              </label>
              <input
                id="update-siren"
                type="text"
                value={siren}
                onChange={(e) => setSiren(e.target.value)}
                placeholder="9 chiffres"
                className={inputClass}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass} htmlFor="update-siret">
                SIRET
              </label>
              <input
                id="update-siret"
                type="text"
                value={siret}
                onChange={(e) => setSiret(e.target.value)}
                placeholder="14 chiffres"
                className={inputClass}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass} htmlFor="update-vat">
                N° TVA
              </label>
              <input
                id="update-vat"
                type="text"
                value={vatNumber}
                onChange={(e) => setVatNumber(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass} htmlFor="update-naf">
                Code NAF
              </label>
              <input
                id="update-naf"
                type="text"
                value={nafCode}
                onChange={(e) => setNafCode(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className={labelClass} htmlFor="update-registration-date">
              Date d'immatriculation
            </label>
            <input
              id="update-registration-date"
              type="date"
              value={registrationDate}
              onChange={(e) => setRegistrationDate(e.target.value)}
              className={inputClass}
            />
          </div>
        </>
      ) : (
        <p className="text-xs text-gray-400">
          Les informations d'immatriculation s'activeront une fois ta société immatriculée.
        </p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </form>
  )
}
