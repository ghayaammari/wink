import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  checkNameAvailability,
  getNameAvailabilityHistory,
  type NameAvailabilityCheckRead,
} from "../api/nameAvailabilityApi"
import { getMyProject, type ProjectRead } from "../api/projectApi"
import {
  getRoadmap,
  updateRoadmapItemStatut,
  uploadRoadmapProof,
  type RoadmapItemRead,
  type RoadmapItemSettableStatut,
} from "../api/roadmapApi"
import GroupeNodes from "../components/roadmap/GroupeNodes"
import RoadmapPathView from "../components/roadmap/RoadmapPathView"
import RoadmapViewToggle from "../components/roadmap/RoadmapViewToggle"
import StepDetailPopup from "../components/roadmap/StepDetailPopup"
import type { RoadmapViewMode } from "../components/roadmap/roadmapLayout"

type LoadState = "loading" | "ready" | "not_applicable" | "error"

/**
 * Plan d'action pré-création — roadmap visuelle des nœuds d'EPIC-01, groupée
 * par étape (voir "Wink — Plan d'action pré-création : spécification"). V1
 * uniquement : pas de bouton "Explain more" (V2, dépend du copilot) ni de
 * lancement direct d'un service EPIC-01 (V3) — voir section 6 de la spec.
 *
 * Condition d'affichage : `project.project_type === "not_created"` (une
 * startup déjà créée a dépassé cette phase). Vérifiée ici via son propre
 * GET /projects/me plutôt que via MyProjectLayout — cette page n'est pas
 * dans le sous-arbre "Mon projet" (nav de premier niveau, voir App.tsx).
 *
 * Trois modes d'affichage au choix (RoadmapViewToggle) : "Graphe" et
 * "Sentier vertical" (cartes de phase repliables, voir GroupeNodes +
 * roadmapLayout.computeGroupLayout) et "Parcours" (chemin vertical continu
 * sans accordéon, voir RoadmapPathView + roadmapLayout.computeFullPathLayout).
 * Popup de détail commun aux trois (StepDetailPopup) qui porte les actions
 * (marquer fait, déposer une preuve) — ces actions ne sont plus inline dans
 * la liste comme avant.
 */
export default function PlanActionPage() {
  const { accessToken } = useAuth()
  const [state, setState] = useState<LoadState>("loading")
  const [project, setProject] = useState<ProjectRead | null>(null)
  const [items, setItems] = useState<RoadmapItemRead[]>([])
  const [nameAvailabilityHistory, setNameAvailabilityHistory] = useState<NameAvailabilityCheckRead[]>([])
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<RoadmapViewMode>("graphe")
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  async function refresh() {
    if (!accessToken) return
    const current = await getMyProject(accessToken)
    setProject(current)
    if (!current || current.project_type !== "not_created") {
      setState("not_applicable")
      return
    }
    // En parallèle : l'historique des vérifications de nom (service 1.1.2) est
    // indépendant de la roadmap elle-même, pas besoin de les enchaîner.
    const [roadmap, nameChecks] = await Promise.all([
      getRoadmap(accessToken, current.id),
      getNameAvailabilityHistory(accessToken, current.id),
    ])
    setItems(roadmap)
    setNameAvailabilityHistory(nameChecks)
    setState("ready")
  }

  useEffect(() => {
    refresh().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger le plan d'action.")
      setState("error")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage
  }, [accessToken])

  async function handleToggleDone(nodeId: string, statut: RoadmapItemSettableStatut) {
    if (!accessToken || !project) return
    // D'autres étapes peuvent avoir changé de statut côté serveur suite à un
    // déverrouillage en cascade (voir roadmap_service._cascade_unlock) — la
    // réponse ne renvoie que l'étape modifiée, donc on recharge la liste
    // complète plutôt que de patcher localement un seul item, pour ne jamais
    // afficher un état devenu incohérent avec la cascade. Le popup, dérivé de
    // `items` par `selectedNodeId`, se met à jour automatiquement.
    await updateRoadmapItemStatut(accessToken, project.id, nodeId, statut)
    await refresh()
  }

  async function handleUploadProof(nodeId: string, file: File) {
    if (!accessToken || !project) return
    await uploadRoadmapProof(accessToken, project.id, nodeId, file)
    await refresh()
  }

  async function handleCheckNameAvailability(nomTeste: string) {
    if (!accessToken || !project) return
    // Même logique que handleToggleDone/handleUploadProof : on recharge tout
    // plutôt que de patcher l'historique localement, pour rester simple et
    // cohérent avec le reste de la page.
    await checkNameAvailability(accessToken, project.id, nomTeste)
    await refresh()
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "not_applicable") {
    return (
      <div className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-gray-900">Plan d'action</h1>
        <p className="text-sm text-gray-500">
          {project
            ? "Ta startup est déjà créée : cette roadmap ne s'applique qu'aux projets pas encore créés."
            : "Termine d'abord l'onboarding pour accéder à ton plan d'action."}
        </p>
      </div>
    )
  }

  const groupes = Array.from(new Set(items.map((item) => item.groupe)))
  const selectedItem = items.find((item) => item.node_id === selectedNodeId) ?? null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Plan d'action</h1>
        <RoadmapViewToggle value={viewMode} onChange={setViewMode} />
      </div>

      {viewMode === "parcours" ? (
        <RoadmapPathView items={items} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
      ) : (
        <div className="flex flex-col gap-3">
          {groupes.map((groupe, index) => (
            <GroupeNodes
              key={groupe}
              groupe={groupe}
              items={items.filter((item) => item.groupe === groupe)}
              viewMode={viewMode}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
              defaultOpen={index === 0}
            />
          ))}
        </div>
      )}

      {selectedItem && (
        <StepDetailPopup
          item={selectedItem}
          allItems={items}
          onClose={() => setSelectedNodeId(null)}
          onToggleDone={handleToggleDone}
          onUploadProof={handleUploadProof}
          nameAvailabilityHistory={nameAvailabilityHistory}
          onCheckNameAvailability={handleCheckNameAvailability}
        />
      )}
    </div>
  )
}
