import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  listPendingValidation,
  submitValidation,
  type AdministrativeGuideValidationItem,
} from "../api/administrativeGuidesValidationApi"

/**
 * Dashboard de validation humaine des guides web collectés pour l'agent
 * réglementaire (pacte_fondateurs, pre_depot — Incrément 1). Même page
 * autonome que LegalTextsValidationPage (pas de DashboardLayout/Sidebar,
 * outil interne non rattaché à un acteur).
 *
 * Contrairement aux `legal_texts` : pas d'action "corriger" (pas de choix de
 * chunking à inverser ici, voir administrative_guides_service.py) — juste
 * "Valider" (passe en valide_humain, backend) et "Ignorer" (retire de la
 * vue locale sans appel API, pour les pages jugées trop pauvres — reste en
 * `extrait_automatique` côté base, réapparaît si la page est rechargée).
 */
export default function AdministrativeGuidesValidationPage() {
  const { accessToken } = useAuth()
  const [items, setItems] = useState<AdministrativeGuideValidationItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken) return
    listPendingValidation(accessToken)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger les guides."))
  }, [accessToken])

  function handleRemoved(id: string) {
    setItems((prev) => (prev ? prev.filter((item) => item.id !== id) : prev))
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-8 py-10">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Validation des guides administratifs</h1>
        <p className="text-sm text-gray-500">
          Relecture des pages web collectées (agent réglementaire, Incrément 1) avant passage en {"valide_humain"}.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {items === null ? (
        <p className="text-sm text-gray-500">Chargement...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-500">Aucun guide en attente de relecture.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <AdministrativeGuideCard key={item.id} item={item} onRemoved={handleRemoved} />
          ))}
        </div>
      )}
    </div>
  )
}

interface AdministrativeGuideCardProps {
  item: AdministrativeGuideValidationItem
  onRemoved: (id: string) => void
}

function AdministrativeGuideCard({ item, onRemoved }: AdministrativeGuideCardProps) {
  const { accessToken } = useAuth()
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleValider() {
    if (!accessToken) return
    setIsSaving(true)
    setError(null)
    try {
      await submitValidation(accessToken, item.id)
      onRemoved(item.id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "L'action a échoué.")
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          {item.titre ?? item.source_url}
          <span className="ml-2 font-normal text-gray-500">— {item.domaine}</span>
        </h3>
        <span className="text-xs text-gray-400">{item.longueur_caracteres} caractères</span>
      </div>

      <p className="mt-1 truncate text-xs text-gray-400">
        {item.source_nom} —{" "}
        <a href={item.source_url} target="_blank" rel="noreferrer" className="underline">
          {item.source_url}
        </a>
      </p>

      <div className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
        {item.texte_brut}
      </div>

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={() => onRemoved(item.id)}
          disabled={isSaving}
          className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-50"
        >
          Ignorer
        </button>
        <button
          type="button"
          onClick={handleValider}
          disabled={isSaving}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSaving ? "Validation..." : "✓ Valider"}
        </button>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}
