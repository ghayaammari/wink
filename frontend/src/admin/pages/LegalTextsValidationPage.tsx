import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  listPendingValidation,
  submitValidation,
  type LegalTextValidationItem,
  type ValidationAction,
} from "../api/legalTextsValidationApi"

/**
 * Dashboard de validation humaine (Phase 1.5, service 1.1.1 — Étapes 1.5.2/
 * 1.5.3 du plan Notion). Outil interne, pas rattaché à un acteur
 * (entrepreneur/chercheur/investisseur) — voir la remarque dans App.tsx sur
 * pourquoi cette page n'utilise pas DashboardLayout/Sidebar : ces deux
 * composants sont construits autour du système de profil par acteur ("Mon
 * profil", déconnexion liée au compte) qui n'a pas de sens ici. Page
 * autonome avec son propre en-tête minimal.
 *
 * Une ligne validée/corrigée quitte la liste immédiatement (elle n'est plus
 * `extrait_automatique` côté back, donc ne réapparaîtrait plus après un
 * rechargement — retirée ici tout de suite pour éviter l'incohérence
 * visuelle entre-temps).
 */
export default function LegalTextsValidationPage() {
  const { accessToken } = useAuth()
  const [items, setItems] = useState<LegalTextValidationItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken) return
    listPendingValidation(accessToken)
      .then(setItems)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger les articles."))
  }, [accessToken])

  function handleResolved(id: string) {
    setItems((prev) => (prev ? prev.filter((item) => item.id !== id) : prev))
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-8 py-10">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Validation des textes de loi</h1>
        <p className="text-sm text-gray-500">
          Relecture des articles collectés (service 1.1.1) avant passage en {"valide_humain"}.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {items === null ? (
        <p className="text-sm text-gray-500">Chargement...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-500">Aucun article en attente de relecture.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {items.map((item) => (
            <LegalTextCard key={item.id} item={item} onResolved={handleResolved} />
          ))}
        </div>
      )}
    </div>
  )
}

interface LegalTextCardProps {
  item: LegalTextValidationItem
  onResolved: (id: string) => void
}

function LegalTextCard({ item, onResolved }: LegalTextCardProps) {
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
      setError(err instanceof ApiError ? err.message : "L'action a échoué.")
      setIsSaving(null)
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          Article {item.article_numero ?? "—"}
          {item.forme_juridique_concernee.length > 0 && (
            <span className="ml-2 font-normal text-gray-500">— {item.forme_juridique_concernee.join(", ")}</span>
          )}
        </h3>
        <span className="text-xs text-gray-400">
          {item.longueur_caracteres} caractères — {item.nb_alineas_detectes} alinéa(s) détecté(s)
        </span>
      </div>

      <div className="mt-3 max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
        {item.texte_brut}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-gray-500">
          Suggestion de chunking : <span className="font-medium text-gray-700">{item.chunking_suggere}</span>
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleAction("valider")}
            disabled={isSaving !== null}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
          >
            {isSaving === "valider" ? "Validation..." : "✓ Valider"}
          </button>
          <button
            type="button"
            onClick={() => handleAction("corriger")}
            disabled={isSaving !== null}
            className="rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-50"
          >
            {isSaving === "corriger"
              ? "Correction..."
              : `✗ Corriger → ${item.chunking_suggere === "aucun" ? "par_alinea" : "aucun"}`}
          </button>
        </div>
      </div>

      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}
