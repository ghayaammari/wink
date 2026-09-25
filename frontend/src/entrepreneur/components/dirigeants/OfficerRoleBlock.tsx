import type { CompanyOfficerRead, ProjectAssociateRead } from "../../api/projectApi"
import OfficerRow from "./OfficerRow"
import type { RoleConfig } from "./officerRoles"

interface Props {
  config: RoleConfig
  officers: CompanyOfficerRead[]
  associes: ProjectAssociateRead[]
  onAdd: () => void
  onEdit: (officer: CompanyOfficerRead) => void
  onDelete: (officer: CompanyOfficerRead) => Promise<void>
}

/**
 * Un bloc par rôle sur la page Dirigeants. Bouton d'ajout masqué quand le
 * rôle est à titulaire unique et déjà pourvu (même règle que le backend).
 * Bord orange tant qu'un rôle obligatoire (Président) est vide.
 */
export default function OfficerRoleBlock({ config, officers, associes, onAdd, onEdit, onDelete }: Props) {
  const manquant = config.obligatoire && officers.length === 0
  const peutAjouter = config.multiple || officers.length === 0

  return (
    <section
      className={`flex flex-col gap-3 rounded-lg border bg-white p-5 ${
        manquant ? "border-amber-300" : "border-gray-200"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{config.titre}</h2>
          <p className="mt-0.5 text-xs text-gray-500">{config.aide}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
            config.obligatoire ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-500"
          }`}
        >
          {config.obligatoire ? "obligatoire" : "facultatif"}
        </span>
      </div>

      {officers.map((o) => (
        <OfficerRow key={o.id} officer={o} associes={associes} onEdit={() => onEdit(o)} onDelete={() => onDelete(o)} />
      ))}

      {manquant && (
        <p className="text-xs text-amber-700">Désignez le Président : il est obligatoire dans vos statuts.</p>
      )}

      {peutAjouter && (
        <button
          type="button"
          onClick={onAdd}
          className="self-start rounded-lg border border-dashed border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:border-indigo-400 hover:text-indigo-700"
        >
          + {config.ajouter}
        </button>
      )}
    </section>
  )
}
