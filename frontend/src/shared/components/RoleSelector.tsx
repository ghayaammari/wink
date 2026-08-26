import type { Role } from "../api/authApi"

const ROLES: { value: Role; label: string }[] = [
  { value: "entrepreneur", label: "Entrepreneur" },
  { value: "chercheur", label: "Chercheur" },
  { value: "investisseur", label: "Investisseur" },
]

interface RoleSelectorProps {
  value: Role | null
  onChange: (role: Role) => void
}

/** Écran 1 du questionnaire — choix du rôle, partagé par signup email et Google. */
export default function RoleSelector({ value, onChange }: RoleSelectorProps) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-gray-700">Je suis...</p>
      <div className="grid grid-cols-3 gap-2">
        {ROLES.map((role) => (
          <button
            key={role.value}
            type="button"
            onClick={() => onChange(role.value)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
              value === role.value
                ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                : "border-gray-300 text-gray-700 hover:border-gray-400"
            }`}
          >
            {role.label}
          </button>
        ))}
      </div>
    </div>
  )
}
