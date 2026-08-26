import { type FormEvent, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { ApiError, resetPassword } from "../api/authApi"

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get("token")
  const [newPassword, setNewPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!token) return

    setError(null)
    setIsSubmitting(true)
    try {
      await resetPassword({ token, new_password: newPassword })
      setSuccess(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  // Cas limite : quelqu'un arrive sur /reset-password sans passer par le lien
  // reçu par email (favori, lien tronqué, copier-coller incomplet).
  if (!token) {
    return (
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-4 text-center">
        <p className="text-sm text-red-600">Lien invalide — aucun token trouvé dans l'URL.</p>
        <Link to="/forgot-password" className="text-sm font-medium text-indigo-600 hover:underline">
          Redemander un lien
        </Link>
      </div>
    )
  }

  if (success) {
    return (
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-4 text-center">
        <p className="text-sm text-gray-700">Mot de passe mis à jour. Tu peux te connecter.</p>
        <button
          type="button"
          onClick={() => navigate("/login")}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Se connecter
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold text-gray-900">Nouveau mot de passe</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <input
          type="password"
          placeholder="Nouveau mot de passe (8 caractères minimum)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
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
          {isSubmitting ? "Mise à jour..." : "Réinitialiser le mot de passe"}
        </button>
      </form>
    </div>
  )
}
