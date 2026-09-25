import { useState, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import {
  updateLegalProfile,
  verifyLegalProfile,
  type ProjectLegalProfileRead,
  type ProjectLegalProfileUpdate,
} from "../api/projectApi"
import StatutsRedactionFields, {
  initialStatutsFields,
  statutsFieldsToPayload,
  validateStatutsFields,
} from "./StatutsRedactionFields"
import VerificationStatusBadge from "./VerificationStatusBadge"

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
  /** Appelé pour fermer la modale — au clic sur "Annuler"/"Fermer" ci-dessous,
   * mais aussi par le "×" natif de `Modal` (voir ProjectLegalInfoPage.tsx). Un
   * seul callback plutôt que `onSaved`/`onCancel` séparés : le parent doit de
   * toute façon rafraîchir le profil légal à chaque fermeture, quel que soit
   * le chemin — bug réel rencontré quand seul le bouton "Fermer" interne
   * déclenchait ce rafraîchissement, pas le "×" de la modale (qui utilisait
   * encore l'ancien `onCancel`, jamais rafraîchi). Rafraîchir même si rien
   * n'a changé est sans risque (un GET de plus), donc pas besoin de
   * distinguer les deux cas côté formulaire. */
  onClose: () => void
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
 *
 * Après la sauvegarde (PATCH), si un SIREN est enregistré (Parcours B),
 * déclenche la vraie vérification (POST .../legal-profile/verify) et affiche
 * son résultat (3 badges) SOUS le formulaire, sans jamais le faire disparaître
 * — le formulaire reste visible et modifiable, l'utilisateur peut re-corriger
 * un champ et ré-enregistrer sans perdre le contexte. Version revue après
 * retour utilisateur : la première version remplaçait tout le formulaire par
 * le panneau de résultat, jugée trop brutale.
 *
 * La sauvegarde et la vérification sont 2 appels séparés (voir
 * legal_verification_service.py) : un échec de vérification (API externe
 * indisponible) ne doit jamais remettre en cause la sauvegarde, déjà réussie.
 */
export default function UpdateLegalProfileForm({
  projectId,
  legalProfile,
  isCreated,
  accessToken,
  onClose,
}: UpdateLegalProfileFormProps) {
  const [legalName, setLegalName] = useState(legalProfile?.legal_name ?? "")
  const [legalForm, setLegalForm] = useState(legalProfile?.legal_form ?? "")
  const [registrationNumber, setRegistrationNumber] = useState(legalProfile?.registration_number ?? "")
  const [siren, setSiren] = useState(legalProfile?.siren ?? "")
  const [siret, setSiret] = useState(legalProfile?.siret ?? "")
  const [vatNumber, setVatNumber] = useState(legalProfile?.vat_number ?? "")
  const [nafCode, setNafCode] = useState(legalProfile?.naf_code ?? "")
  const [registrationDate, setRegistrationDate] = useState(legalProfile?.registration_date ?? "")
  // Service 1.1.4 : champs lus automatiquement par les statuts (objet social,
  // durée, capital, sigle…) -- bloc dédié, voir StatutsRedactionFields.tsx.
  // Toujours éditables : ils se décident AVANT l'immatriculation, donc pas
  // liés à `isCreated`.
  const [statutsFields, setStatutsFields] = useState(() => initialStatutsFields(legalProfile))

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // "form" = formulaire éditable ; "verifying" = sauvegardé, vérification en cours
  // (Parcours B avec SIREN) ; "result" = panneau de badges affiché.
  const [phase, setPhase] = useState<"form" | "verifying" | "result">("form")
  const [verifiedProfile, setVerifiedProfile] = useState<ProjectLegalProfileRead | null>(null)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    // siren/siret doivent être OMIS du payload si vides, jamais envoyés comme "" :
    // ce sont les 2 seuls champs validés côté backend par un pattern strict
    // (`^\d{9}$`/`^\d{14}$`, voir project_legal_profile_schemas.py) qui rejette une
    // chaîne vide avec un 422 — une chaîne vide n'est pas None, donc le champ
    // "optionnel" n'est pas ignoré par la validation. Bug réel rencontré : SIRET
    // laissé vide → 422 sur ce PATCH. Les autres champs (legal_name, legal_form,
    // registration_number, vat_number, naf_code) n'ont qu'une contrainte de
    // longueur max — une chaîne vide y est valide, envoyée telle quelle comme
    // avant (permet de les vider volontairement). Même traitement que
    // `registration_date` juste en dessous, qui gérait déjà ce cas pour lui seul.
    const erreurStatuts = validateStatutsFields(statutsFields)
    if (erreurStatuts) {
      setError(erreurStatuts)
      return
    }

    const sirenOrOmit = siren.trim() === "" ? undefined : siren.trim()
    const siretOrOmit = siret.trim() === "" ? undefined : siret.trim()

    const payload: ProjectLegalProfileUpdate = {
      legal_name: legalName.trim(),
      legal_form: legalForm.trim(),
      ...statutsFieldsToPayload(statutsFields),
      ...(isCreated
        ? {
            registration_number: registrationNumber.trim(),
            ...(sirenOrOmit !== undefined ? { siren: sirenOrOmit } : {}),
            ...(siretOrOmit !== undefined ? { siret: siretOrOmit } : {}),
            vat_number: vatNumber.trim(),
            naf_code: nafCode.trim(),
            ...(registrationDate.trim() !== "" ? { registration_date: registrationDate.trim() } : {}),
          }
        : {}),
    }

    setIsSubmitting(true)
    try {
      const saved = await updateLegalProfile(accessToken, projectId, payload)
      if (isCreated && saved.siren) {
        setPhase("verifying")
        try {
          const verified = await verifyLegalProfile(accessToken, projectId)
          setVerifiedProfile(verified)
        } catch (err) {
          // La sauvegarde a réussi — seule la vérification a échoué (ex: API
          // externe indisponible, 503). On le signale sans faire perdre la saisie.
          setVerifyError(err instanceof ApiError ? err.message : "Vérification indisponible pour le moment.")
        }
        setPhase("result")
      } else {
        onClose()
      }
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

      <StatutsRedactionFields values={statutsFields} onChange={setStatutsFields} />

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
          onClick={onClose}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          {phase === "form" ? "Annuler" : "Fermer"}
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {phase === "verifying" ? "Vérification..." : isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>

      {/* Résultat de la vérification — sous les boutons, jamais à la place du
       * formulaire (voir docstring en haut du fichier). */}
      {(phase === "verifying" || phase === "result") && (
        <div className="mt-2 flex flex-col gap-3 border-t border-gray-100 pt-4">
          <h3 className="text-sm font-medium text-gray-700">Résultat de la vérification</h3>

          {phase === "verifying" && <p className="text-sm text-gray-500">Vérification en cours...</p>}

          {phase === "result" &&
            (verifiedProfile ? (
              <>
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Dénomination</span>
                    <VerificationStatusBadge status={verifiedProfile.denomination_verification_status} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">SIREN / SIRET</span>
                    <VerificationStatusBadge status={verifiedProfile.immatriculation_verification_status} />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">Kbis</span>
                    <VerificationStatusBadge status={verifiedProfile.kbis_verification_status} />
                  </div>
                </div>
                {verifiedProfile.denomination_verification_status === "incoherent" && (
                  // Pas de nom officiel cité ici (ex: "« WINK TECHNOLOGIES SAS »") :
                  // verify_legal_profile ne le renvoie/stocke pas actuellement, voir
                  // documentation-implementation.md — ajout possible si besoin.
                  <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Le nom officiellement enregistré diffère de celui saisi. Vos informations sont enregistrées
                    quand même — corrigez si c'est une erreur de saisie, ou ignorez si c'est normal.
                  </p>
                )}
                {verifiedProfile.immatriculation_verification_status === "incoherent" && (
                  // Le SIREN est bon (sinon on n'arriverait jamais ici, voir
                  // verify_legal_profile) mais le SIRET saisi ne correspond pas à
                  // celui du siège social trouvé — signalé séparément du nom.
                  <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Le SIREN correspond bien à une entreprise active, mais le SIRET saisi ne correspond pas à celui
                    de son siège social. Vos informations sont enregistrées quand même — corrigez si c'est une
                    erreur de saisie, ou ignorez si c'est normal (ex: un établissement secondaire).
                  </p>
                )}
              </>
            ) : (
              <p className="text-sm text-amber-700">{verifyError}</p>
            ))}
        </div>
      )}
    </form>
  )
}
