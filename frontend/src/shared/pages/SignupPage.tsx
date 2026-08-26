import { GoogleLogin } from "@react-oauth/google"
import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ApiError, type Role, signup, signupGoogle } from "../api/authApi"
import RoleSelector from "../components/RoleSelector"
import { useAuth } from "../context/AuthContext"

type SignupStep = "role" | "method" | "email"

export default function SignupPage() {
  // Un seul bloc affiché à la fois — rôle, puis méthode, puis formulaire —
  // plutôt que tout empiler sur la même page. `role` reste en mémoire même
  // après être passé à l'étape suivante, pour ne pas le perdre si l'utilisateur
  // revient en arrière avec "← Retour".
  const [step, setStep] = useState<SignupStep>("role")
  const [role, setRole] = useState<Role | null>(null)
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { setTokens } = useAuth()
  const navigate = useNavigate()

  async function handleEmailSubmit(event: FormEvent) {
    event.preventDefault()
    if (!role) return

    setError(null)
    setIsSubmitting(true)
    try {
      const tokens = await signup({ email, password, role, first_name: firstName, last_name: lastName })
      setTokens(tokens)
      navigate("/")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleGoogleSuccess(credential: string) {
    if (!role) return

    setError(null)
    try {
      const tokens = await signupGoogle({ id_token: credential, role })
      setTokens(tokens)
      navigate("/")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold text-gray-900">Créer un compte</h1>

      {step === "role" && (
        <RoleSelector
          value={role}
          onChange={(newRole) => {
            setRole(newRole)
            setStep("method")
          }}
        />
      )}

      {step === "method" && (
        <div className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setStep("role")}
            className="self-start text-sm text-gray-500 hover:underline"
          >
            ← Retour
          </button>

          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={(res) => res.credential && handleGoogleSuccess(res.credential)}
              onError={() => setError("La connexion Google a échoué.")}
              text="signup_with"
              shape="pill"
            />
          </div>

          <button
            type="button"
            onClick={() => setStep("email")}
            className="rounded-full border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
          >
            S'inscrire avec email
          </button>

          {error && <p className="text-center text-sm text-red-600">{error}</p>}
        </div>
      )}

      {step === "email" && (
        <form onSubmit={handleEmailSubmit} className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setStep("method")}
            className="self-start text-sm text-gray-500 hover:underline"
          >
            ← Retour
          </button>

          <div className="grid grid-cols-2 gap-3">
            <input
              type="text"
              placeholder="Prénom"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <input
              type="text"
              placeholder="Nom"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <input
            type="password"
            placeholder="Mot de passe (8 caractères minimum)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Création..." : "Créer mon compte"}
          </button>
        </form>
      )}

      <p className="text-center text-sm text-gray-500">
        Déjà un compte ?{" "}
        <Link to="/login" className="font-medium text-indigo-600 hover:underline">
          Se connecter
        </Link>
      </p>
    </div>
  )
}
