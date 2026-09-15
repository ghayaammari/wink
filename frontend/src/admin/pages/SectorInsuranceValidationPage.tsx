import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  listPendingValidation,
  submitValidation,
  type SectorInsuranceValidationItem,
  type ValidationAction,
} from "../api/sectorInsuranceValidationApi"

/**
 * Dashboard de validation humaine des recommandations d'assurance sectorielles
 * (service 1.1.10). Meme pattern que LegalTextsValidationPage : page autonome,
 * pas rattachee a un acteur.
 */
export default function SectorInsuranceValidationPage() {
  const { accessToken } = useAuth()
  const [items, setItems] = useState<SectorInsuranceValidationItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken) return
    listPendingValidation(accessToken)
      .then(setItems)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Impossible de charger les recommandations."),
      )
  }, [accessToken])

  function handleResolved(id: string) {
    setItems((prev) => (prev ? prev.filter((item) => item.id !== id) : prev))
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-8 py-10">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Validation des assurances sectorielles</h1>
        <p className="text-sm text-gray-500">
          Relecture des recommandations collectees (service 1.1.10) avant passage en {"valide_humain"}.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {items === null ? (
        <p className="text-sm text-gray-500">Chargement...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-500">Aucune recommandation en attente de relecture.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <InsuranceCard key={item.id} item={item} onResolved={handleResolved} />
          ))}
        </div>
      )}
    </div>
  )
}

interface InsuranceCardProps {
  item: SectorInsuranceValidationItem
  onResolved: (id: string) => void
}

function InsuranceCard({ item, onResolved }: InsuranceCardProps) {
  const { accessToken } = useAuth()
  const [isSaving, setIsSaving] = useState<ValidationAction | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleAction(action: ValidationAction) {
    if (!accessToken) return
    setIsSaving(action)
    setError(null)
    try {
      await submitValidation(accessToken, item.id, action)
      onResolved(item.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "L'action a echoue.")
      setIsSaving(null)
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          {item.secteur}
          <span className="ml-2 font-normal text-gray-500">— {item.type_assurance}</span>
        </h3>
        <span className="text-xs text-gray-400">{item.longueur_caracteres} caracteres</span>
      </div>

      <div className="mt-2 flex items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            item.a_base_legale ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"
          }`}
        >
          {item.a_base_legale ? "Base legale" : "Recommandation"}
        </span>
        {item.source_nom && <span className="text-xs text-gray-500">Source : {item.source_nom}</span>}
      </div>

      {item.texte_brut && (
        <div className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
          {item.texte_brut}
        </div>
      )}

      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => handleAction("valider")}
          disabled={isSaving !== null}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSaving === "valider" ? "Validation..." : "Valider"}
        </button>
        <button
          type="button"
          onClick={() => handleAction("corriger")}
          disabled={isSaving !== null}
          className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-50"
        >
          {isSaving === "corriger"
            ? "Correction..."
            : `Corriger → ${item.a_base_legale ? "Recommandation" : "Base legale"}`}
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}
