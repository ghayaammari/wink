import { GoogleLogin } from "@react-oauth/google"
import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ApiError, login, loginGoogle } from "../api/authApi"
import { useAuth } from "../context/AuthContext"

type LoginStep = "method" | "email"

export default function LoginPage() {
  // Même pattern que SignupPage : un seul bloc affiché à la fois — choix de
  // la méthode, puis formulaire — pas de rôle à choisir ici (il vient déjà du
  // compte existant côté backend).
  const [step, setStep] = useState<LoginStep>("method")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { setTokens } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const tokens = await login({ email, password })
      setTokens(tokens)
      navigate("/")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleGoogleSuccess(credential: string) {
    setError(null)
    try {
      const tokens = await loginGoogle({ id_token: credential })
      setTokens(tokens)
      navigate("/")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold text-gray-900">Se connecter</h1>

      {step === "method" && (
        <div className="flex flex-col gap-3">
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={(res) => res.credential && handleGoogleSuccess(res.credential)}
              onError={() => setError("La connexion Google a échoué.")}
              shape="pill"
            />
          </div>

          <button
            type="button"
            onClick={() => setStep("email")}
            className="rounded-full border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
          >
            Se connecter avec email
          </button>

          {error && <p className="text-center text-sm text-red-600">{error}</p>}
        </div>
      )}

      {step === "email" && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setStep("method")}
            className="self-start text-sm text-gray-500 hover:underline"
          >
            ← Retour
          </button>

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
            placeholder="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="text-right">
            <Link to="/forgot-password" className="text-xs text-indigo-600 hover:underline">
              Mot de passe oublié ?
            </Link>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Connexion..." : "Se connecter"}
          </button>
        </form>
      )}

      <p className="text-center text-sm text-gray-500">
        Pas encore de compte ?{" "}
        <Link to="/signup" className="font-medium text-indigo-600 hover:underline">
          Créer un compte
        </Link>
      </p>
    </div>
  )
}
