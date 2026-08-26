import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { logout } from "../api/authApi"
import { getStoredRefreshToken, useAuth } from "../context/AuthContext"

// Placeholder — remplacé par le vrai flow d'onboarding au prochain incrément.
export default function HomePage() {
  const { clearTokens } = useAuth()
  const navigate = useNavigate()
  const [isSigningOut, setIsSigningOut] = useState(false)

  async function handleSignOut() {
    setIsSigningOut(true)
    const refreshToken = getStoredRefreshToken()
    try {
      if (refreshToken) {
        await logout({ refresh_token: refreshToken })
      }
    } catch {
      // /auth/logout est idempotent côté backend (revoke_refresh_token ne lève
      // jamais si le token est déjà invalide/expiré) — même si l'appel réseau
      // échoue ici (backend down, etc.), on déconnecte quand même localement :
      // laisser l'utilisateur "connecté" dans ce cas serait pire.
    } finally {
      clearTokens()
      navigate("/login")
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8 text-center text-gray-600">
      <p>Connecté — l'onboarding arrive au prochain incrément.</p>
      <button
        type="button"
        onClick={handleSignOut}
        disabled={isSigningOut}
        className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
      >
        {isSigningOut ? "Déconnexion..." : "Se déconnecter"}
      </button>
    </div>
  )
}
