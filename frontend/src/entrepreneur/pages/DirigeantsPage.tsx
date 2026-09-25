import { useCallback, useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { useAuth } from "../../shared/context/AuthContext"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import {
  deleteOfficer,
  getAssociates,
  getOfficers,
  type CompanyOfficerRead,
  type ProjectAssociateRead,
  type RoleDirigeant,
} from "../api/projectApi"
import OfficerFormModal from "../components/dirigeants/OfficerFormModal"
import OfficerRoleBlock from "../components/dirigeants/OfficerRoleBlock"
import { ROLES_DIRIGEANTS } from "../components/dirigeants/officerRoles"
import type { MyProjectOutletContext } from "./MyProjectLayout"

/**
 * Page « Dirigeants » de Mon projet (service 1.1.4, lot 5 du 24/09/2026) —
 * page à part, comme « Équipe & capital » : Équipe & capital dit QUI
 * POSSÈDE la société, cette page dit QUI LA DIRIGE (`company_officers`),
 * repris automatiquement dans les statuts (art. 39-41, 44, annexe III).
 *
 * Un bloc par rôle ; chaque action (ajouter / modifier / supprimer) est
 * enregistrée immédiatement, puis la liste est rechargée depuis le serveur
 * (source de vérité, pas de mise à jour locale à maintenir en parallèle).
 */

type Edition = { role: RoleDirigeant; officer: CompanyOfficerRead | null }

export default function DirigeantsPage() {
  const { accessToken } = useAuth()
  const { project } = useOutletContext<MyProjectOutletContext>()

  const [officers, setOfficers] = useState<CompanyOfficerRead[] | null>(null)
  const [associes, setAssocies] = useState<ProjectAssociateRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [edition, setEdition] = useState<Edition | null>(null)

  const charger = useCallback(() => {
    if (!accessToken) return
    Promise.all([getOfficers(accessToken, project.id), getAssociates(accessToken, project.id)])
      .then(([o, a]) => {
        setOfficers(o)
        setAssocies(a)
        setLoadError(null)
      })
      .catch(() => setLoadError("Impossible de charger les dirigeants pour le moment. Rechargez la page."))
  }, [accessToken, project.id])

  useEffect(() => {
    charger()
  }, [charger])

  async function supprimer(officer: CompanyOfficerRead) {
    // L'erreur remonte à OfficerRow, qui l'affiche dans la ligne concernée.
    await deleteOfficer(accessToken!, project.id, officer.id)
    charger()
  }

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (officers === null) return <LoadingSpinner />

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Dirigeants</h1>
        <p className="mt-1 text-sm text-gray-500">
          Les personnes qui dirigent la société. Elles sont reprises automatiquement dans vos statuts.
        </p>
      </div>

      {ROLES_DIRIGEANTS.map((config) => (
        <OfficerRoleBlock
          key={config.role}
          config={config}
          officers={officers.filter((o) => o.role === config.role)}
          associes={associes}
          onAdd={() => setEdition({ role: config.role, officer: null })}
          onEdit={(officer) => setEdition({ role: config.role, officer })}
          onDelete={supprimer}
        />
      ))}

      {edition && accessToken && (
        <OfficerFormModal
          role={edition.role}
          officer={edition.officer}
          associes={associes}
          projectId={project.id}
          accessToken={accessToken}
          onClose={() => setEdition(null)}
          onSaved={() => {
            setEdition(null)
            charger()
          }}
        />
      )}
    </div>
  )
}
