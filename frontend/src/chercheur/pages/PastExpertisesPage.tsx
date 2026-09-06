import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  createPastExpertise,
  listPastExpertises,
  updatePastExpertise,
  type PastExpertise,
  type PastExpertiseCreate,
  type PastExpertiseUpdate,
} from "../api/researcherPastExpertiseApi"

/**
 * "Mes expertises passées" — table facultative researcher_past_expertises,
 * jamais demandée à l'onboarding, saisie librement à tout moment. Page à
 * part entière (accès direct via la navigation, pas une sous-section de
 * "Mes travaux") — voir CHERCHEUR_NAV_ITEMS dans App.tsx.
 *
 * Pas de workflow de validation (contrairement aux champs extraits de
 * HAL/OpenAlex) : une expertise saisie manuellement est confirmée par
 * construction, donc pas de Confirmer/Rejeter ici, juste une liste + un
 * formulaire d'ajout.
 */
export default function PastExpertisesPage() {
  const { accessToken } = useAuth()
  const [expertises, setExpertises] = useState<PastExpertise[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)

  useEffect(() => {
    if (!accessToken) return
    listPastExpertises(accessToken)
      .then(setExpertises)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger tes expertises."))
  }, [accessToken])

  function handleCreated(expertise: PastExpertise) {
    setExpertises((prev) => (prev ? [expertise, ...prev] : [expertise]))
    setIsFormOpen(false)
  }

  function handleUpdated(expertise: PastExpertise) {
    setExpertises((prev) => (prev ? prev.map((e) => (e.id === expertise.id ? expertise : e)) : prev))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Mes expertises passées</h1>
        <button
          type="button"
          onClick={() => setIsFormOpen((open) => !open)}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700"
        >
          {isFormOpen ? "Annuler" : "Ajouter une expertise"}
        </button>
      </div>

      {isFormOpen && <ExpertiseForm onCreated={handleCreated} onError={setError} />}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {expertises === null ? (
        <p className="text-sm text-gray-500">Chargement...</p>
      ) : expertises.length === 0 ? (
        !isFormOpen && (
          <p className="text-sm text-gray-500">Aucune expertise déclarée pour l'instant — ajoute la première ci-dessus.</p>
        )
      ) : (
        <div className="flex flex-col gap-3">
          {expertises.map((expertise) => (
            <ExpertiseCard key={expertise.id} expertise={expertise} onUpdated={handleUpdated} />
          ))}
        </div>
      )}
    </div>
  )
}

interface ExpertiseFormProps {
  onCreated: (expertise: PastExpertise) => void
  onError: (message: string) => void
}

function ExpertiseForm({ onCreated, onError }: ExpertiseFormProps) {
  const { accessToken } = useAuth()
  const [organizationName, setOrganizationName] = useState("")
  const [domain, setDomain] = useState("")
  const [missionType, setMissionType] = useState("")
  const [periodLabel, setPeriodLabel] = useState("")
  const [description, setDescription] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  async function handleSubmit() {
    if (!accessToken || !organizationName.trim()) return
    setIsSaving(true)
    try {
      const data: PastExpertiseCreate = {
        organization_name: organizationName.trim(),
        domain: domain.trim() || null,
        mission_type: missionType.trim() || null,
        period_label: periodLabel.trim() || null,
        description: description.trim() || null,
      }
      const expertise = await createPastExpertise(accessToken, data)
      onCreated(expertise)
      // Réinitialise le formulaire — utile si le chercheur enchaîne l'ajout
      // de plusieurs expertises sans fermer/rouvrir le formulaire entre deux.
      setOrganizationName("")
      setDomain("")
      setMissionType("")
      setPeriodLabel("")
      setDescription("")
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "L'ajout de l'expertise a échoué.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Entreprise / startup concernée</label>
        <input
          type="text"
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-700">Secteur</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-700">Type de mission</label>
          <input
            type="text"
            value={missionType}
            onChange={(e) => setMissionType(e.target.value)}
            placeholder="Conseil, audit, accompagnement..."
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Période</label>
        <input
          type="text"
          value={periodLabel}
          onChange={(e) => setPeriodLabel(e.target.value)}
          placeholder="Ex : 2022-2023"
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={isSaving || !organizationName.trim()}
        className="self-start rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {isSaving ? "Ajout..." : "Ajouter"}
      </button>
    </div>
  )
}

interface ExpertiseCardProps {
  expertise: PastExpertise
  onUpdated: (expertise: PastExpertise) => void
}

function ExpertiseCard({ expertise, onUpdated }: ExpertiseCardProps) {
  const [isEditing, setIsEditing] = useState(false)

  if (isEditing) {
    return (
      <ExpertiseEditForm
        expertise={expertise}
        onSaved={(updated) => {
          onUpdated(updated)
          setIsEditing(false)
        }}
        onCancel={() => setIsEditing(false)}
      />
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">{expertise.organization_name}</h3>
        <button type="button" onClick={() => setIsEditing(true)} className="text-xs font-medium text-indigo-600">
          Modifier
        </button>
      </div>

      <dl className="mt-2 grid grid-cols-3 gap-x-4 gap-y-2 text-sm text-gray-600">
        <div>
          <dt className="text-xs font-medium text-gray-500">Secteur</dt>
          <dd>{expertise.domain ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">Type de mission</dt>
          <dd>{expertise.mission_type ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">Période</dt>
          <dd>{expertise.period_label ?? "—"}</dd>
        </div>
      </dl>

      {expertise.description && (
        <div className="mt-3 border-t border-gray-100 pt-2">
          <p className="text-xs font-medium text-gray-500">Description</p>
          <p className="text-sm text-gray-700">{expertise.description}</p>
        </div>
      )}
    </div>
  )
}

interface ExpertiseEditFormProps {
  expertise: PastExpertise
  onSaved: (expertise: PastExpertise) => void
  onCancel: () => void
}

/** Formulaire d'édition pré-rempli avec les valeurs actuelles — mêmes champs
 * que ExpertiseForm (création), mais PATCH au lieu de POST, et pas de reset
 * après sauvegarde (on quitte le mode édition, voir onSaved). Pas de
 * workflow de validation ici, comme pour la création : la valeur modifiée
 * est effective immédiatement. */
function ExpertiseEditForm({ expertise, onSaved, onCancel }: ExpertiseEditFormProps) {
  const { accessToken } = useAuth()
  const [organizationName, setOrganizationName] = useState(expertise.organization_name)
  const [domain, setDomain] = useState(expertise.domain ?? "")
  const [missionType, setMissionType] = useState(expertise.mission_type ?? "")
  const [periodLabel, setPeriodLabel] = useState(expertise.period_label ?? "")
  const [description, setDescription] = useState(expertise.description ?? "")
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSave() {
    if (!accessToken || !organizationName.trim()) return
    setIsSaving(true)
    setError(null)
    try {
      const data: PastExpertiseUpdate = {
        organization_name: organizationName.trim(),
        domain: domain.trim() || null,
        mission_type: missionType.trim() || null,
        period_label: periodLabel.trim() || null,
        description: description.trim() || null,
      }
      const updated = await updatePastExpertise(accessToken, expertise.id, data)
      onSaved(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La modification a échoué.")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-4">
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Entreprise / startup concernée</label>
        <input
          type="text"
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-700">Secteur</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-700">Type de mission</label>
          <input
            type="text"
            value={missionType}
            onChange={(e) => setMissionType(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Période</label>
        <input
          type="text"
          value={periodLabel}
          onChange={(e) => setPeriodLabel(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-gray-700">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onCancel} className="text-xs font-medium text-gray-500">
          Annuler
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving || !organizationName.trim()}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
        >
          {isSaving ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </div>
  )
}