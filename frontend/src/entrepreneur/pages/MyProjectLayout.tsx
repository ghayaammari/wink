import { useEffect, useState } from "react"
import { Navigate, Outlet } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { getFieldValues, getMyProject, type ProjectFieldValueRead, type ProjectRead } from "../api/projectApi"

export interface MyProjectOutletContext {
  project: ProjectRead
  fieldValues: ProjectFieldValueRead[]
  /** Recharge project + fieldValues depuis le backend — à appeler seulement
   * après un événement qui change réellement la donnée serveur (import de
   * document, résolution/ignorer d'un champ). Une simple navigation entre les
   * 4 pages de "Mon Projet" ne doit jamais en déclencher un. */
  refresh: () => Promise<void>
}

/**
 * Route parent des 4 pages "Mon Projet" (landing + Informations générales/
 * légales, Vitrine publique) — voir App.tsx. Fait le fetch de `project` et
 * `fieldValues` UNE SEULE FOIS pour tout le sous-arbre, exposé aux pages
 * enfants via `useOutletContext<MyProjectOutletContext>()`.
 *
 * Avant ce fichier, chacune des 4 pages refaisait son propre GET /projects/me
 * + GET /field-values à chaque navigation entre elles (jusqu'à 8 appels
 * réseau, et jusqu'à 12 requêtes SQL à cause du calcul de complétion attaché
 * à /projects/me) alors que la donnée ne change pas tant qu'on reste dans ce
 * flux — voir la discussion "chargement lourd". Centraliser le fetch ici fait
 * tomber ça à 2 appels réseau pour visiter les 4 écrans.
 */
export default function MyProjectLayout() {
  const { accessToken } = useAuth()
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [fieldValues, setFieldValues] = useState<ProjectFieldValueRead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function refresh() {
    if (!accessToken) return
    const current = await getMyProject(accessToken)
    setProject(current)
    if (!current) return
    setFieldValues(await getFieldValues(accessToken, current.id))
  }

  useEffect(() => {
    setIsLoading(true)
    refresh()
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger ton projet."))
      .finally(() => setIsLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [accessToken])

  if (isLoading) return <p className="text-sm text-gray-500">Chargement...</p>
  if (error) return <p className="text-sm text-red-600">{error}</p>
  // Cas limite : accès direct à une URL "mon-projet/..." avant d'avoir terminé
  // l'écran 2 de l'onboarding (pas encore de projet).
  if (!project) return <Navigate to="/onboarding" replace />

  return <Outlet context={{ project, fieldValues, refresh } satisfies MyProjectOutletContext} />
}
