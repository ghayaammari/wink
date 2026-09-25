import { useCallback, useEffect, useState } from "react"
import Field from "../../shared/components/Field"
import Modal from "../../shared/components/Modal"
import SectionCard from "../../shared/components/SectionCard"
import {
  getAssociates,
  getOfficers,
  type CompanyOfficerRead,
  type ProjectAssociateRead,
  type RoleDirigeant,
} from "../api/projectApi"
import CompanyOfficersForm from "./CompanyOfficersForm"

/**
 * Carte « Dirigeants » de la page DirigeantsPage (service 1.1.4, lot 5
 * du 24/09/2026) : lecture des dirigeants désignés + bouton « Modifier » qui
 * ouvre l'éditeur (CompanyOfficersForm). Ces dirigeants sont repris
 * automatiquement dans les statuts (art. 39-41, 44, annexe III) — c'est le
 * seul endroit de l'appli où ils se saisissent.
 *
 * Composant autonome (charge ses propres données) : la page n'a pas à
 * connaître `company_officers`.
 */

const LIBELLES_ROLE: Record<RoleDirigeant, string> = {
  president: "Président",
  directeur_general: "Directeur Général",
  membre_comite: "Membre du Comité de Direction",
  mandataire: "Mandataire (actes avant immatriculation)",
}

function identite(o: CompanyOfficerRead, associes: ProjectAssociateRead[]): string {
  if (o.associate_id) {
    const a = associes.find((x) => x.id === o.associate_id)
    // Associé supprimé depuis (FK ON DELETE SET NULL côté base -> ne devrait
    // pas arriver ici, mais un état intermédiaire reste possible).
    return a ? `${a.nom_complet} (associé)` : "(associé introuvable)"
  }
  const nom = o.type_personne === "personne_morale" ? o.denomination_sociale : o.nom_complet
  return nom || "(nom non renseigné)"
}

interface Props {
  projectId: string
  accessToken: string
}

export default function CompanyOfficersSection({ projectId, accessToken }: Props) {
  const [officers, setOfficers] = useState<CompanyOfficerRead[] | null>(null)
  const [associes, setAssocies] = useState<ProjectAssociateRead[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)

  const charger = useCallback(() => {
    Promise.all([getOfficers(accessToken, projectId), getAssociates(accessToken, projectId)])
      .then(([o, a]) => {
        setOfficers(o)
        setAssocies(a)
        setLoadError(null)
      })
      .catch(() => setLoadError("Impossible de charger les dirigeants pour le moment."))
  }, [accessToken, projectId])

  useEffect(() => {
    charger()
  }, [charger])

  function fermer(saved: boolean) {
    setIsModalOpen(false)
    if (saved) charger()
  }

  const sansPresident = officers !== null && !officers.some((o) => o.role === "president")

  return (
    <>
      <SectionCard
        title="Dirigeants"
        action={
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            disabled={officers === null}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:border-gray-400 disabled:opacity-50"
          >
            Modifier
          </button>
        }
      >
        <div className="flex flex-col gap-4">
          {loadError && <p className="text-xs text-red-600">{loadError}</p>}
          {officers?.map((o) => (
            <Field
              key={o.id}
              label={LIBELLES_ROLE[o.role]}
              value={identite(o, associes) + (o.duree_fonctions ? ` — pour ${o.duree_fonctions}` : "")}
            />
          ))}
          {officers !== null && officers.length === 0 && <p className="text-sm text-gray-500">Aucun dirigeant désigné.</p>}
          {sansPresident && (
            <p className="text-xs text-amber-700">
              Désignez au moins le Président avant de rédiger vos statuts : il y est repris automatiquement.
            </p>
          )}
        </div>
      </SectionCard>

      {isModalOpen && officers !== null && (
        <Modal title="Dirigeants" onClose={() => fermer(false)}>
          <CompanyOfficersForm
            projectId={projectId}
            accessToken={accessToken}
            officers={officers}
            associes={associes}
            onClose={fermer}
          />
        </Modal>
      )}
    </>
  )
}
