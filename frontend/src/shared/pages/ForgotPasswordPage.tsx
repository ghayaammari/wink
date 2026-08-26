import { type FormEvent, useState } from "react"
import { Link } from "react-router-dom"
import { ApiError, forgotPassword } from "../api/authApi"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      // La réponse est volontairement générique (même si l'email n'existe pas) —
      // voir request_password_reset côté backend. Rien à faire de spécial ici.
      const res = await forgotPassword({ email })
      setMessage(res.detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold text-gray-900">Mot de passe oublié</h1>

      {message ? (
        <p className="text-sm text-gray-700">{message}</p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <p className="text-sm text-gray-500">
            Entre ton email, on t'envoie un lien pour réinitialiser ton mot de passe.
          </p>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? "Envoi..." : "Envoyer le lien"}
          </button>
        </form>
      )}

      <p className="text-center text-sm text-gray-500">
        <Link to="/login" className="font-medium text-indigo-600 hover:underline">
          Retour à la connexion
        </Link>
      </p>
    </div>
  )
}
