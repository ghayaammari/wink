import { type FormEvent, useEffect, useState } from "react"
import { ApiError, getCurrentUser, updateCurrentUser, type UserRead } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  getMyInvestorProfile,
  updateInvestorProfile,
  type InvestorProfileRead,
  type InvestorType,
} from "../api/investorProfileApi"

const INVESTOR_TYPE_OPTIONS: { value: InvestorType; label: string }[] = [
  { value: "vc", label: "VC (capital-risque)" },
  { value: "business_angel", label: "Business angel" },
  { value: "family_office", label: "Family office" },
  { value: "corporate_vc", label: "Corporate VC" },
  { value: "fonds_public", label: "Fonds public (ex: Bpifrance)" },
  { value: "autre", label: "Autre" },
]

const INVESTOR_TYPE_LABELS: Record<InvestorType, string> = Object.fromEntries(
  INVESTOR_TYPE_OPTIONS.map((o) => [o.value, o.label]),
) as Record<InvestorType, string>

/** Un seul bouton "Modifier" bascule à la fois le compte (prénom/nom/email)
 * et le profil investisseur métier en édition — pas de rôle affiché (voir
 * échange du 06/09/2026). Changer l'email exige de ressaisir le mot de passe
 * actuel (voir auth_service.update_user) ; ce champ n'apparaît que si
 * l'email a été modifié. */
export default function InvestorProfilePage() {
  const { accessToken } = useAuth()
  const [user, setUser] = useState<UserRead | null>(null)
  const [profile, setProfile] = useState<InvestorProfileRead | null>(null)
  const [isEditing, setIsEditing] = useState(false)

  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [currentPassword, setCurrentPassword] = useState("")

  const [investorType, setInvestorType] = useState<InvestorType | "">("")
  const [organizationName, setOrganizationName] = useState("")
  const [investmentThesis, setInvestmentThesis] = useState("")
  const [contactEmail, setContactEmail] = useState("")

  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  function loadAll() {
    if (!accessToken) return
    getCurrentUser(accessToken)
      .then((data) => {
        setUser(data)
        setFirstName(data.first_name ?? "")
        setLastName(data.last_name ?? "")
        setEmail(data.email)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger ton compte."))
    getMyInvestorProfile(accessToken)
      .then((data) => {
        setProfile(data)
        setInvestorType(data.investor_type ?? "")
        setOrganizationName(data.organization_name ?? "")
        setInvestmentThesis(data.investment_thesis ?? "")
        setContactEmail(data.contact_email ?? "")
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger ton profil."))
  }

  useEffect(loadAll, [accessToken])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !user) return

    setError(null)
    setIsSaving(true)
    try {
      const emailChanged = email.trim().toLowerCase() !== user.email.toLowerCase()

      await updateCurrentUser(accessToken, {
        first_name: firstName.trim() || undefined,
        last_name: lastName.trim() || undefined,
        email: emailChanged ? email.trim() : undefined,
        current_password: emailChanged ? currentPassword : undefined,
      })

      const updatedProfile = await updateInvestorProfile(accessToken, {
        investor_type: investorType || undefined,
        organization_name: organizationName.trim() || null,
        investment_thesis: investmentThesis.trim() || null,
        contact_email: contactEmail.trim() || null,
      })

      setProfile(updatedProfile)
      setCurrentPassword("")
      setIsEditing(false)
      loadAll()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La mise à jour a échoué.")
    } finally {
      setIsSaving(false)
    }
  }

  if (error && !profile) return <p className="text-sm text-red-600">{error}</p>
  if (!user || !profile) return <p className="text-sm text-gray-500">Chargement...</p>

  const emailWillChange = email.trim().toLowerCase() !== user.email.toLowerCase()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Mon profil investisseur</h1>
        <button
          type="button"
          onClick={() => setIsEditing((e) => !e)}
          className="text-sm font-medium text-indigo-600"
        >
          {isEditing ? "Annuler" : "Modifier"}
        </button>
      </div>

      {isEditing ? (
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Informations personnelles</h2>
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-gray-600">Prénom</span>
                  <input
                    type="text"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-gray-600">Nom</span>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-gray-600">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
              {emailWillChange && (
                <label className="flex flex-col gap-1">
                  <span className="text-xs font-medium text-gray-600">
                    Mot de passe actuel (requis pour changer d'email)
                  </span>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </label>
              )}
            </div>
          </section>

          <section className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Profil investisseur</h2>
            <div className="flex flex-col gap-4">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-gray-600">Type d'investisseur</span>
                <select
                  value={investorType}
                  onChange={(e) => setInvestorType(e.target.value as InvestorType)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700"
                >
                  <option value="">Sélectionner...</option>
                  {INVESTOR_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-gray-600">Organisation</span>
                <input
                  type="text"
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-gray-600">Thèse d'investissement</span>
                <textarea
                  value={investmentThesis}
                  onChange={(e) => setInvestmentThesis(e.target.value)}
                  rows={4}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-gray-600">Email de contact</span>
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </label>
            </div>
          </section>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isSaving}
            className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {isSaving ? "Enregistrement..." : "Enregistrer"}
          </button>
        </form>
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
            <h2 className="mb-3 text-sm font-semibold text-gray-900">Profil investisseur</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm text-gray-600">
              <div>
                <dt className="font-medium text-gray-500">Type d'investisseur</dt>
                <dd>{profile.investor_type ? INVESTOR_TYPE_LABELS[profile.investor_type] : "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Organisation</dt>
                <dd>{profile.organization_name ?? "Investisseur individuel"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Email de contact</dt>
                <dd>{profile.contact_email ?? "—"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="font-medium text-gray-500">Thèse d'investissement</dt>
                <dd>{profile.investment_thesis ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Complétion du profil</dt>
                <dd>{profile.profile_completion}</dd>
              </div>
            </dl>
          </section>
        </>
      )}
    </div>
  )
}