import { type FormEvent, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { completeOnboarding, type InvestorType } from "../api/investorProfileApi"

const INVESTOR_TYPE_OPTIONS: { value: InvestorType; label: string }[] = [
  { value: "vc", label: "VC (capital-risque)" },
  { value: "business_angel", label: "Business angel" },
  { value: "family_office", label: "Family office" },
  { value: "corporate_vc", label: "Corporate VC" },
  { value: "fonds_public", label: "Fonds public (ex: Bpifrance)" },
  { value: "autre", label: "Autre" },
]

/** Onboarding investisseur — parcours linéaire (pas de branchement comme
 * chercheur/entrepreneur), un seul appel POST /investisseur/onboarding.
 * investor_type est obligatoire (voir InvestorOnboardingRequest côté
 * backend). Au moins un des deux champs restants (thèse ou email de
 * contact) est aussi requis pour soumettre — validé ici pour un message
 * immédiat sans aller-retour serveur. */
export default function InvestorOnboardingPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()
  const [investorType, setInvestorType] = useState<InvestorType | "">("")
  const [organizationName, setOrganizationName] = useState("")
  const [investmentThesis, setInvestmentThesis] = useState("")
  const [contactEmail, setContactEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken) return

    if (!investorType) {
      setError("Sélectionne ton type d'investisseur.")
      return
    }
    if (!investmentThesis.trim() && !contactEmail.trim()) {
      setError("Renseigne au moins ta thèse d'investissement ou ton email de contact.")
      return
    }

    setError(null)
    setIsSubmitting(true)
    try {
      await completeOnboarding(accessToken, {
        investor_type: investorType,
        organization_name: organizationName.trim() || null,
        investment_thesis: investmentThesis.trim() || null,
        contact_email: contactEmail.trim() || null,
      })
      navigate("/investisseur", { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? formatApiErrorMessage(err.message) : "La complétion du profil a échoué.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg p-8">
      <h1 className="mb-1 text-xl font-semibold text-gray-900">Bienvenue</h1>
      <p className="mb-6 text-sm text-gray-500">
        Quelques informations pour démarrer — tout reste modifiable plus tard depuis ton profil.
      </p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">Quel type d'investisseur es-tu ?</span>
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
          <span className="text-xs font-medium text-gray-600">
            Représentez-vous une organisation ? (optionnel)
          </span>
          <input
            type="text"
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            placeholder="Nom du fonds ou de l'organisation"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">
            Décrivez votre thèse d'investissement : quels types de startups recherchez-vous ?
          </span>
          <textarea
            value={investmentThesis}
            onChange={(e) => setInvestmentThesis(e.target.value)}
            rows={4}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-600">
            Quelle adresse email souhaitez-vous que les startups utilisent pour vous répondre ?
          </span>
          <input
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            placeholder="contact@fonds.com"
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting}
          className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Terminer"}
        </button>
      </form>
    </div>
  )
}

/** FastAPI renvoie le detail d'une 422 Pydantic comme un tableau d'objets
 * ({loc, msg, type, ...}), pas une simple string — ApiError.message peut
 * donc être ce tableau sérialisé en "[object Object]" si on l'affiche tel
 * quel. On en extrait un message lisible dans ce cas, sinon on garde la
 * string telle quelle (cas des erreurs métier volontaires, ex:
 * "investment_thesis ou contact_email requis..."). */
function formatApiErrorMessage(message: unknown): string {
  if (typeof message === "string") return message
  if (Array.isArray(message)) {
    return message
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item)))
      .join(" ")
  }
  return "La complétion du profil a échoué."
}