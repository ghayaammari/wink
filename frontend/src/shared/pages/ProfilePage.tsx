import { useEffect, useState } from "react"
import { ApiError, getCurrentUser, type UserRead } from "../api/authApi"
import Field from "../components/Field"
import SectionCard from "../components/SectionCard"
import { useAuth } from "../context/AuthContext"

const ROLE_LABELS: Record<UserRead["role"], string> = {
  entrepreneur: "Entrepreneur",
  chercheur: "Chercheur",
  investisseur: "Investisseur",
}

/**
 * "Mon profil" — service transverse aux 3 acteurs (pas un service numéroté à
 * part dans la table I0 : email + données personnelles du compte `users`, pas
 * du profil métier propre à chaque acteur — voir MyProjectPage pour ça côté
 * entrepreneur). Lecture seule pour I0 : GET /auth/me est le seul endpoint
 * exposé côté backend pour l'instant, aucune route de modification.
 */
export default function ProfilePage() {
  const { accessToken } = useAuth()
  const [user, setUser] = useState<UserRead | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken) return
    getCurrentUser(accessToken)
      .then(setUser)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Impossible de charger ton profil."),
      )
  }, [accessToken])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!user) return <p className="text-sm text-gray-500">Chargement...</p>

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold text-gray-900">Mon profil</h1>

      <SectionCard title="Informations personnelles">
        <dl className="grid grid-cols-2 gap-4">
          <Field label="Prénom" value={user.first_name ?? "—"} />
          <Field label="Nom" value={user.last_name ?? "—"} />
          <Field label="Email" value={user.email} />
          <Field label="Rôle" value={ROLE_LABELS[user.role]} />
          <Field label="Membre depuis" value={new Date(user.created_at).toLocaleDateString("fr-FR")} />
        </dl>
      </SectionCard>
    </div>
  )
}
