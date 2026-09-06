import { useEffect, useState } from "react"
import { ApiError, getCurrentUser, updateCurrentUser, type UserRead } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  getMyResearcherProfile,
  triggerExpertiseSummary,
  triggerResearchWorkSummary,
  updateResearcherProfile,
  type ResearcherProfileRead,
} from "../api/researcherProfileApi"
import { validateField, type FieldValue } from "../api/researchWorkApi"

const FIELD_NAME_LABELS: Record<string, string> = {
  affiliation: "Affiliation",
  research_domains: "Domaines de recherche",
  expertise_summary: "Résumé d'expertise (généré)",
  research_work_summary: "Résumé des travaux de recherche (généré)",
}

type ValidateAction = "confirm" | "reject" | "edit"

function groupByFieldName(values: FieldValue[]): Map<string, FieldValue[]> {
  const groups = new Map<string, FieldValue[]>()
  for (const value of values) {
    const group = groups.get(value.field_name) ?? []
    group.push(value)
    groups.set(value.field_name, group)
  }
  return groups
}

/** Un seul bouton "Modifier" bascule à la fois le compte (prénom/nom/email)
 * et le profil de recherche métier en édition — pas de rôle affiché (voir
 * échange du 06/09/2026). Changer l'email exige de ressaisir le mot de passe
 * actuel (voir auth_service.update_user) ; ce champ n'apparaît que si
 * l'email a été modifié. */
export default function ResearcherProfileDetailsPage() {
  const { accessToken } = useAuth()
  const [user, setUser] = useState<UserRead | null>(null)
  const [profile, setProfile] = useState<ResearcherProfileRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isEditing, setIsEditing] = useState(false)
  const [isReviewingPending, setIsReviewingPending] = useState(false)
  const [isBulkProcessing, setIsBulkProcessing] = useState(false)

  function loadAll() {
    if (!accessToken) return
    getCurrentUser(accessToken)
      .then(setUser)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger ton compte."))
    getMyResearcherProfile(accessToken)
      .then(setProfile)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger ton profil."))
  }

  useEffect(() => {
    loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de token
  }, [accessToken])

  async function handleValidate(fieldValueId: string, action: ValidateAction, newValue?: string) {
    if (!accessToken) return
    try {
      await validateField(accessToken, fieldValueId, action, newValue)
      loadAll()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La validation a échoué.")
    }
  }

  async function handleBulkValidate(action: "confirm" | "reject", fields: FieldValue[]) {
    if (!accessToken || fields.length === 0) return
    setIsBulkProcessing(true)
    try {
      for (const field of fields) {
        await validateField(accessToken, field.id, action)
      }
      loadAll()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `L'action groupée (${action}) a échoué.`)
    } finally {
      setIsBulkProcessing(false)
    }
  }

  if (error && !profile) return <p className="text-sm text-red-600">{error}</p>
  if (!user || !profile) return <p className="text-sm text-gray-500">Chargement...</p>

  const generatedFieldValues = profile.generated_field_values ?? []
  const pendingFields = generatedFieldValues.filter((f) => f.validation_status === "pending_confirmation")

  const pendingExpertise = generatedFieldValues.find(
    (f) => f.field_name === "expertise_summary" && f.validation_status === "pending_confirmation",
  )
  const pendingResearchWork = generatedFieldValues.find(
    (f) => f.field_name === "research_work_summary" && f.validation_status === "pending_confirmation",
  )

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Mon profil</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setIsReviewingPending(true)}
            className="rounded-lg bg-white px-3 py-2 text-sm font-medium text-amber-700 ring-1 ring-amber-300 transition hover:bg-amber-50"
          >
            {pendingFields.length > 0
              ? `Consulter les champs à confirmer (${pendingFields.length})`
              : "Consulter les champs à confirmer"}
          </button>
          <button
            type="button"
            onClick={() => setIsEditing((e) => !e)}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
          >
            {isEditing ? "Annuler" : "Modifier"}
          </button>
        </div>
      </div>

      {isEditing ? (
        <ProfileEditForm
          user={user}
          profile={profile}
          onSaved={() => {
            setIsEditing(false)
            loadAll()
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <>
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Informations personnelles</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm text-gray-600">
              <div>
                <dt className="font-medium text-gray-500">Prénom</dt>
                <dd>{user.first_name ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Nom</dt>
                <dd>{user.last_name ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Email</dt>
                <dd>{user.email}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Membre depuis</dt>
                <dd>{new Date(user.created_at).toLocaleDateString("fr-FR")}</dd>
              </div>
            </dl>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Profil de recherche</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm text-gray-600">
              <div>
                <dt className="font-medium text-gray-500">ORCID</dt>
                <dd>{profile.orcid_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Affiliation</dt>
                <dd>{profile.affiliation ?? "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="font-medium text-gray-500">Domaines de recherche</dt>
                <dd>{profile.research_domains.length > 0 ? profile.research_domains.join(", ") : "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="mb-1 font-medium text-gray-500">Résumé d'expertise</dt>
                <dd className="flex items-start justify-between gap-3">
                  <span>
                    {profile.expertise_summary ?? pendingExpertise?.field_value ?? "Pas encore généré."}
                    {!profile.expertise_summary && pendingExpertise && (
                      <span className="ml-2 text-xs font-medium text-amber-600">(en attente de confirmation)</span>
                    )}
                  </span>
                  <SummaryButton kind="expertise" onReload={loadAll} />
                </dd>
              </div>
              <div className="col-span-2">
                <dt className="mb-1 font-medium text-gray-500">Résumé des travaux de recherche</dt>
                <dd className="flex items-start justify-between gap-3">
                  <span>
                    {profile.research_work_summary ?? pendingResearchWork?.field_value ?? "Pas encore généré."}
                    {!profile.research_work_summary && pendingResearchWork && (
                      <span className="ml-2 text-xs font-medium text-amber-600">(en attente de confirmation)</span>
                    )}
                  </span>
                  <SummaryButton kind="research_work" onReload={loadAll} />
                </dd>
              </div>
            </dl>
          </section>
        </>
      )}

      {isReviewingPending && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-6"
          onClick={() => setIsReviewingPending(false)}
        >
          <div
            className="my-8 w-full max-w-2xl rounded-lg bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Champs à confirmer</h2>
              <button
                type="button"
                onClick={() => setIsReviewingPending(false)}
                className="rounded-lg px-2 py-1 text-sm text-gray-500 hover:bg-gray-100"
              >
                Fermer
              </button>
            </div>

            {pendingFields.length === 0 ? (
              <p className="text-sm text-gray-500">Aucun champ à confirmer pour l'instant.</p>
            ) : (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-medium text-amber-700">
                    {pendingFields.length} champ(s) à confirmer
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleBulkValidate("confirm", pendingFields)}
                      disabled={isBulkProcessing}
                      className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-green-200 hover:bg-green-50 disabled:opacity-50"
                    >
                      {isBulkProcessing ? "Traitement..." : "Tout confirmer"}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBulkValidate("reject", pendingFields)}
                      disabled={isBulkProcessing}
                      className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50"
                    >
                      {isBulkProcessing ? "Traitement..." : "Tout rejeter"}
                    </button>
                  </div>
                </div>

                {Array.from(groupByFieldName(pendingFields)).map(([fieldName, values]) =>
                  values.map((field) => (
                    <PendingFieldRow key={field.id} field={field} onValidate={handleValidate} />
                  )),
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

interface PendingFieldRowProps {
  field: FieldValue
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
}

function PendingFieldRow({ field, onValidate }: PendingFieldRowProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [value, setValue] = useState(field.field_value)
  const [isSaving, setIsSaving] = useState(false)

  async function handleSaveEdit() {
    setIsSaving(true)
    try {
      await onValidate(field.id, "edit", value)
      setIsEditing(false)
    } finally {
      setIsSaving(false)
    }
  }

  if (isEditing) {
    return (
      <div className="rounded-lg bg-amber-50 px-3 py-2">
        <p className="mb-1 text-xs font-medium text-amber-800">
          {FIELD_NAME_LABELS[field.field_name] ?? field.field_name}
        </p>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={3}
          className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
        />
        <div className="mt-2 flex justify-end gap-2">
          <button type="button" onClick={() => setIsEditing(false)} className="text-xs text-gray-500">
            Annuler
          </button>
          <button
            type="button"
            onClick={handleSaveEdit}
            disabled={isSaving || !value.trim()}
            className="rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {isSaving ? "Enregistrement..." : "Enregistrer et confirmer"}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-amber-50 px-3 py-2">
      <div className="min-w-0">
        <p className="text-xs font-medium text-amber-800">
          {FIELD_NAME_LABELS[field.field_name] ?? field.field_name}
        </p>
        <p className="text-sm text-gray-700">{field.field_value}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50"
        >
          Modifier
        </button>
        <button
          type="button"
          onClick={() => onValidate(field.id, "confirm")}
          className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-green-200 hover:bg-green-50"
        >
          Confirmer
        </button>
        <button
          type="button"
          onClick={() => onValidate(field.id, "reject")}
          className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-50"
        >
          Rejeter
        </button>
      </div>
    </div>
  )
}

interface SummaryButtonProps {
  kind: "expertise" | "research_work"
  onReload: () => void
}

function SummaryButton({ kind, onReload }: SummaryButtonProps) {
  const { accessToken } = useAuth()
  const [status, setStatus] = useState<"idle" | "processing" | "done" | "failed">("idle")

  async function handleClick() {
    if (!accessToken) return
    setStatus("processing")
    try {
      if (kind === "expertise") {
        await triggerExpertiseSummary(accessToken)
      } else {
        await triggerResearchWorkSummary(accessToken)
      }
      setStatus("done")
      window.setTimeout(onReload, 5000)
    } catch {
      setStatus("failed")
    }
  }

  return (
    <div className="shrink-0 text-right">
      <button
        type="button"
        onClick={handleClick}
        disabled={status === "processing"}
        className="text-xs font-medium text-indigo-600 disabled:opacity-50"
      >
        {status === "processing" ? "Génération..." : "Générer"}
      </button>
      {status === "done" && <p className="mt-1 text-xs text-gray-500">Actualisation...</p>}
      {status === "failed" && <p className="mt-1 text-xs text-red-600">Échec.</p>}
    </div>
  )
}

interface ProfileEditFormProps {
  user: UserRead
  profile: ResearcherProfileRead
  onSaved: () => void
  onCancel: () => void
}

function ProfileEditForm({ user, profile, onSaved, onCancel }: ProfileEditFormProps) {
  const { accessToken } = useAuth()

  const [firstName, setFirstName] = useState(user.first_name ?? "")
  const [lastName, setLastName] = useState(user.last_name ?? "")
  const [email, setEmail] = useState(user.email)
  const [currentPassword, setCurrentPassword] = useState("")

  const [orcidId, setOrcidId] = useState(profile.orcid_id ?? "")
  const [affiliation, setAffiliation] = useState(profile.affiliation ?? "")
  const [domainsText, setDomainsText] = useState(profile.research_domains.join(", "))
  const [expertiseSummary, setExpertiseSummary] = useState(profile.expertise_summary ?? "")
  const [researchWorkSummary, setResearchWorkSummary] = useState(profile.research_work_summary ?? "")

  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const emailWillChange = email.trim().toLowerCase() !== user.email.toLowerCase()

  async function handleSave() {
    if (!accessToken) return
    setError(null)
    setIsSaving(true)
    try {
      await updateCurrentUser(accessToken, {
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        email: emailWillChange ? email.trim() : undefined,
        current_password: emailWillChange ? currentPassword : undefined,
      })

      await updateResearcherProfile(accessToken, {
        orcid_id: orcidId.trim() || null,
        affiliation: affiliation.trim() || undefined,
        research_domains: domainsText
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean),
        expertise_summary: expertiseSummary.trim() || undefined,
        research_work_summary: researchWorkSummary.trim() || undefined,
      })
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "L'enregistrement a échoué.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="flex flex-col gap-3 rounded-lg border border-indigo-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900">Informations personnelles</h2>
        <div className="grid grid-cols-2 gap-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-gray-500">Prénom</span>
            <input
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-gray-500">Nom</span>
            <input
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
        {emailWillChange && (
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-gray-500">Mot de passe actuel (requis pour changer d'email)</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
        )}
      </section>

      <section className="flex flex-col gap-3 rounded-lg border border-indigo-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900">Profil de recherche</h2>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">ORCID</span>
          <input
            type="text"
            value={orcidId}
            onChange={(e) => setOrcidId(e.target.value)}
            placeholder="0000-0000-0000-0000"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">Affiliation</span>
          <input
            type="text"
            value={affiliation}
            onChange={(e) => setAffiliation(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">Domaines de recherche (séparés par des virgules)</span>
          <input
            type="text"
            value={domainsText}
            onChange={(e) => setDomainsText(e.target.value)}
            placeholder="IA, biologie, économie"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">Résumé d'expertise</span>
          <textarea
            value={expertiseSummary}
            onChange={(e) => setExpertiseSummary(e.target.value)}
            rows={3}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-gray-500">Résumé des travaux de recherche</span>
          <textarea
            value={researchWorkSummary}
            onChange={(e) => setResearchWorkSummary(e.target.value)}
            rows={3}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>
      </section>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-lg px-3 py-2 text-sm text-gray-500">
          Annuler
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSaving ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </div>
  )
}