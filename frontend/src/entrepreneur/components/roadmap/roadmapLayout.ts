/**
 * Calcul de la disposition (positions + flèches) des nœuds de la roadmap, à
 * partir du graphe de dépendances (`depends_on`, exposé par
 * `RoadmapItemRead` — voir roadmap_service._dependencies_map côté backend).
 *
 * Fichier pur, sans dépendance React ni DOM : testable indépendamment du
 * rendu SVG. Deux algorithmes de disposition, partageant le même calcul de
 * couches (`layerRows`) :
 * - `computeGroupLayout` : disposition en grille (colonnes ou lignes) d'UN
 *   groupe, consommée par RoadmapGraphCanvas (vues "Graphe"/"Sentier",
 *   rendues dans les cartes de phase repliables de GroupeNodes).
 * - `computeFullPathLayout` : disposition en chemin vertical continu de
 *   TOUTE la roadmap, groupe par groupe avec une étiquette entre chaque
 *   section, consommée par RoadmapPathView (vue "Parcours", sans accordéon).
 */
import type { RoadmapItemRead } from "../../api/roadmapApi"

export type GridViewMode = "graphe" | "sentier"
export type RoadmapViewMode = GridViewMode | "parcours"

/**
 * Assigne à chaque nœud une "couche" = 1 + la couche max de ses dépendances
 * internes à `items`, puis regroupe les nœuds par couche. Un nœud sans
 * dépendance interne démarre en couche 0. Utilisé pour les deux vues en
 * grille ET pour la vue parcours (appelé séparément par section/groupe dans
 * ce dernier cas — voir computeFullPathLayout). Pas de détection de cycle :
 * déjà garantie côté seed (`seed_roadmap_nodes._validate_graph`, le graphe
 * est un DAG).
 */
function layerRows(items: RoadmapItemRead[]): RoadmapItemRead[][] {
  const idsInScope = new Set(items.map((item) => item.node_id))
  const byId = new Map(items.map((item) => [item.node_id, item]))
  const layers = new Map<string, number>()

  function layerOf(nodeId: string): number {
    const cached = layers.get(nodeId)
    if (cached !== undefined) return cached
    const item = byId.get(nodeId)
    const localDeps = (item?.depends_on ?? []).filter((depId) => idsInScope.has(depId))
    const layer = localDeps.length === 0 ? 0 : 1 + Math.max(...localDeps.map(layerOf))
    layers.set(nodeId, layer)
    return layer
  }

  items.forEach((item) => layerOf(item.node_id))

  const maxLayer = Math.max(0, ...items.map((item) => layers.get(item.node_id) ?? 0))
  const rows: RoadmapItemRead[][] = Array.from({ length: maxLayer + 1 }, () => [])
  // Ordre stable par `ordre` (les items arrivent déjà triés) au sein d'une
  // même couche.
  items.forEach((item) => rows[layers.get(item.node_id) ?? 0].push(item))
  return rows
}

// --- Vue en grille (Graphe / Sentier), une carte de phase à la fois ---

export interface NodePosition {
  nodeId: string
  x: number
  y: number
}

export interface Edge {
  from: string
  to: string
  path: string
}

export interface GroupLayout {
  positions: NodePosition[]
  edges: Edge[]
  width: number
  height: number
}

export const NODE_WIDTH = 200
export const NODE_HEIGHT = 64
const GAP_MAIN = 56 // écart entre couches (colonnes en mode "graphe", lignes en mode "sentier")
const GAP_CROSS = 20 // écart entre nœuds d'une même couche

function gridEdgePath(x1: number, y1: number, x2: number, y2: number, viewMode: GridViewMode): string {
  if (viewMode === "graphe") {
    const midX = (x1 + x2) / 2
    return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
  }
  const midY = (y1 + y2) / 2
  return `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`
}

/**
 * "graphe" : les couches avancent horizontalement (colonnes), les nœuds
 * d'une couche sont répartis verticalement.
 * "sentier" : les couches avancent verticalement (lignes), les nœuds d'une
 * couche sont répartis horizontalement.
 * Les dépendances vers un autre groupe ne sont jamais dessinées ici (elles
 * traversent une frontière de carte de phase) — le détail reste dans le
 * popup ("Étapes requises").
 */
export function computeGroupLayout(items: RoadmapItemRead[], viewMode: GridViewMode): GroupLayout {
  const rows = layerRows(items)
  const maxCross = Math.max(1, ...rows.map((row) => row.length))
  const crossSpan = maxCross * NODE_WIDTH + (maxCross - 1) * GAP_CROSS

  const positions: NodePosition[] = []
  const positionById = new Map<string, { x: number; y: number }>()

  rows.forEach((row, layerIndex) => {
    const rowSpan = row.length * NODE_WIDTH + (row.length - 1) * GAP_CROSS
    const offset = (crossSpan - rowSpan) / 2
    row.forEach((item, i) => {
      const cross = offset + i * (NODE_WIDTH + GAP_CROSS)
      const main = layerIndex * (NODE_HEIGHT + GAP_MAIN)
      const point = viewMode === "graphe" ? { x: main, y: cross } : { x: cross, y: main }
      positions.push({ nodeId: item.node_id, x: point.x, y: point.y })
      positionById.set(item.node_id, point)
    })
  })

  const idsInGroup = new Set(items.map((item) => item.node_id))
  const edges: Edge[] = []
  items.forEach((item) => {
    item.depends_on
      .filter((depId) => idsInGroup.has(depId))
      .forEach((depId) => {
        const from = positionById.get(depId)
        const to = positionById.get(item.node_id)
        if (!from || !to) return
        const x1 = from.x + (viewMode === "graphe" ? NODE_WIDTH : NODE_WIDTH / 2)
        const y1 = from.y + (viewMode === "graphe" ? NODE_HEIGHT / 2 : NODE_HEIGHT)
        const x2 = to.x + (viewMode === "graphe" ? 0 : NODE_WIDTH / 2)
        const y2 = to.y + (viewMode === "graphe" ? NODE_HEIGHT / 2 : 0)
        edges.push({ from: depId, to: item.node_id, path: gridEdgePath(x1, y1, x2, y2, viewMode) })
      })
  })

  const width = viewMode === "graphe" ? rows.length * (NODE_WIDTH + GAP_MAIN) - GAP_MAIN : crossSpan
  const height = viewMode === "graphe" ? crossSpan : rows.length * (NODE_HEIGHT + GAP_MAIN) - GAP_MAIN

  return { positions, edges, width: Math.max(width, NODE_WIDTH), height: Math.max(height, NODE_HEIGHT) }
}

// --- Vue "Parcours" : toute la roadmap comme un seul chemin vertical ---

export const PATH_ROW_HEIGHT = 84
const PATH_ROW_GAP = 30
const PATH_HEADER_HEIGHT = 30
const PATH_HEADER_GAP_BEFORE = 34
const PATH_HEADER_GAP_AFTER = 20
const PATH_CENTER_X = 350
const PATH_CANVAS_WIDTH = 760

export interface PathNodePosition {
  nodeId: string
  x: number
  y: number
  width: number
}

export interface PathHeader {
  groupe: string
  y: number
}

export interface PathEdge {
  from: string
  to: string
  path: string
  done: boolean
}

export interface FullPathLayout {
  headers: PathHeader[]
  positions: PathNodePosition[]
  edges: PathEdge[]
  width: number
  height: number
}

/** Largeur de carte + décalage horizontal selon le nombre de nœuds
 * parallèles dans une même rangée (rangée "single" = 1, "branch" = 2+) —
 * plus il y a de branches, plus les cartes sont étroites, dans l'esprit du
 * mockup de référence (qui codait ça en dur pour 2 et 3 branches). */
function pathBranchGeometry(count: number): { width: number; lefts: number[] } {
  const width = count <= 1 ? 380 : count === 2 ? 260 : count === 3 ? 220 : 180
  const gap = 20
  const totalWidth = count * width + (count - 1) * gap
  const startX = PATH_CENTER_X - totalWidth / 2
  const lefts = Array.from({ length: count }, (_, i) => startX + i * (width + gap))
  return { width, lefts }
}

function pathEdgePath(x1: number, y1: number, x2: number, y2: number): string {
  return `M ${x1} ${y1} C ${x1} ${y1 + 30}, ${x2} ${y2 - 30}, ${x2} ${y2}`
}

/**
 * Dispose TOUS les nœuds de la roadmap comme un seul chemin vertical
 * continu, groupé par section (`groupe`, dans l'ordre de première
 * apparition selon `ordre`), avec une étiquette entre chaque section — pas
 * d'accordéon ici, voir RoadmapPathView. Même règle que `computeGroupLayout`
 * pour les couches : une dépendance inter-sections n'est pas dessinée comme
 * flèche (reste dans le popup, "Étapes requises"), pour rester cohérent
 * avec le choix déjà fait sur les vues Graphe/Sentier.
 */
export function computeFullPathLayout(items: RoadmapItemRead[]): FullPathLayout {
  const ordered = [...items].sort((a, b) => a.ordre - b.ordre)
  const byId = new Map(ordered.map((item) => [item.node_id, item]))

  const groupeOrder: string[] = []
  ordered.forEach((item) => {
    if (!groupeOrder.includes(item.groupe)) groupeOrder.push(item.groupe)
  })

  const headers: PathHeader[] = []
  const positions: PathNodePosition[] = []
  const positionById = new Map<string, { x: number; y: number; width: number }>()
  let y = 20

  groupeOrder.forEach((groupe) => {
    const groupItems = ordered.filter((item) => item.groupe === groupe)
    const rows = layerRows(groupItems)

    y += PATH_HEADER_GAP_BEFORE
    headers.push({ groupe, y })
    y += PATH_HEADER_HEIGHT + PATH_HEADER_GAP_AFTER

    rows.forEach((row) => {
      const geo = pathBranchGeometry(row.length)
      row.forEach((item, i) => {
        const point = { x: geo.lefts[i], y, width: geo.width }
        positions.push({ nodeId: item.node_id, ...point })
        positionById.set(item.node_id, point)
      })
      y += PATH_ROW_HEIGHT + PATH_ROW_GAP
    })
  })

  const edges: PathEdge[] = []
  ordered.forEach((item) => {
    item.depends_on
      .filter((depId) => byId.get(depId)?.groupe === item.groupe)
      .forEach((depId) => {
        const from = positionById.get(depId)
        const to = positionById.get(item.node_id)
        if (!from || !to) return
        const x1 = from.x + from.width / 2
        const y1 = from.y + PATH_ROW_HEIGHT
        const x2 = to.x + to.width / 2
        const y2 = to.y
        edges.push({
          from: depId,
          to: item.node_id,
          path: pathEdgePath(x1, y1, x2, y2),
          done: byId.get(depId)?.statut === "termine",
        })
      })
  })

  return { headers, positions, edges, width: PATH_CANVAS_WIDTH, height: y + 20 }
}
