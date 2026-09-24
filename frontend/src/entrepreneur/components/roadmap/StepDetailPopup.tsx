import { type ChangeEvent, type FormEvent, useRef, useState } from "react"
import { Link } from "react-router-dom"
import type { NameAvailabilityCheckRead, StatutDenomination, StatutMarque } from "../../api/nameAvailabilityApi"
import type { RoadmapItemRead, RoadmapItemSettableStatut } from "../../api/roadmapApi"

interface StepDetailPopupProps {
  item: RoadmapItemRead
  allItems: RoadmapItemRead[]
  onClose: () => void
  onToggleDone: (nodeId: string, statut: RoadmapItemSettableStatut) => Promise<void>
  onUploadProof: (nodeId: string, file: File) => Promise<void>
  nameAvailabilityHistory: NameAvailabilityCheckRead[]
  onCheckNameAvailability: (nomTeste: string) => Promise<void>
}

// Id du nœud roadmap correspondant au service 1.1.2 (vérificateur croisé de
// disponibilité du nom) — voir wink_roadmap_creation_juridique.json. Un seul
// nœud concerné : pas besoin d'une prop dédiée, ce composant sait déjà lequel.
const NAME_AVAILABILITY_NODE_ID = "e3_verification_disponibilite_nom"

// Nœuds roadmap avec une page de rédaction interactive dédiée — GÉNÉRALISÉ
// (25/09/2026) : c'était un simple id en dur (service 1.1.13 pacte, seul
// nœud concerné) avec un commentaire annonçant explicitement cette table de
// correspondance pour le jour où un 2e nœud (statuts, service 1.1.4) en
// aurait une. C'est fait ici — un 3e nœud de rédaction n'aura qu'une ligne
// à ajouter, pas un nouveau bloc JSX.
const DOCUMENT_GENERATION_NODE_ROUTES: Record<string, { route: string; label: string }> = {
  e4_pacte_fondateurs: { route: "/entrepreneur/mon-projet/pacte-fondateurs-v2", label: "Rédiger le pacte de fondateurs" },
  e5_redaction_statuts: { route: "/entrepreneur/mon-projet/statuts", label: "Rédiger les statuts" },
  // Service 1.1.5 — rédaction de l'annonce + journaux habilités du département.
  e9b_annonce_legale: { route: "/entrepreneur/mon-projet/annonce-legale", label: "Rédiger l'annonce légale" },
}

// Étapes dont la donnée source vit dans "Équipe & capital" (`project_associates`,
// socle partagé Groupe 5 : services 1.1.13 pacte / 1.1.4 statuts / 1.1.6 DBE /
// e21 régime fiscal) — voir TeamCapitalPage. (réalisé par OPENCODE)
const TEAM_CAPITAL_DATA_NODES = new Set([
  "e4_pacte_fondateurs",
  "e5_redaction_statuts",
  "e11_dbe",
  "e21_immatriculation_fiscale",
])

const STATUT_DENOMINATION_LABEL: Record<string, string> = {
  disponible: "libre",
  pris: "pris",
}

const STATUT_DENOMINATION_CLASS: Record<string, string> = {
  disponible: "bg-green-50 text-green-700",
  pris: "bg-red-50 text-red-700",
}

const STATUT_MARQUE_LABEL: Record<string, string> = {
  disponible: "libre",
  risque: "risque",
  pris: "prise",
}

const STATUT_MARQUE_CLASS: Record<string, string> = {
  disponible: "bg-green-50 text-green-700",
  risque: "bg-amber-50 text-amber-700",
  pris: "bg-red-50 text-red-700",
}

// Verdict synthétique (Nom, Marque) -> { ton, libellé, sous-texte} — validé
// avec l'utilisateur via une maquette avant implémentation (voir échange du
// 2026-09-12). Règle métier fixe, indépendante du nom testé : recalculée ici
// à partir des 2 statuts déjà renvoyés par le backend, pas stockée en base.
// Priorité au Nom (bloquant pour l'immatriculation elle-même) ; la Marque ne
// nuance qu'un Nom déjà libre.
type VerdictTone = "green" | "amber" | "red"

interface Verdict {
  tone: VerdictTone
  label: string
  sub: string
}

function verdictCombinaison(statutDenomination: StatutDenomination, statutMarque: StatutMarque): Verdict {
  if (statutDenomination === "pris") {
    return { tone: "red", label: "Nom à changer", sub: "Dénomination déjà prise par une entreprise active" }
  }
  if (statutMarque === "disponible") {
    return { tone: "green", label: "Disponible", sub: "Aucun conflit détecté" }
  }
  return {
    tone: "amber",
    label: "Utilisable avec prudence",
    sub: statutMarque === "pris" ? "Marque déjà déposée" : "Conflit de marque partiel",
  }
}

const VERDICT_BG_CLASS: Record<VerdictTone, string> = {
  green: "bg-green-50",
  amber: "bg-amber-50",
  red: "bg-red-50",
}

const VERDICT_TEXT_CLASS: Record<VerdictTone, string> = {
  green: "text-green-700",
  amber: "text-amber-700",
  red: "text-red-700",
}

function VerdictIcon({ tone }: { tone: VerdictTone }) {
  const className = `h-4 w-4 shrink-0 ${VERDICT_TEXT_CLASS[tone]}`
  if (tone === "green") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
        <circle cx="12" cy="12" r="9" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.5 12.5l2.5 2.5 5-5" />
      </svg>
    )
  }
  if (tone === "amber") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l9.5 16.5a1 1 0 0 1-.87 1.5H3.37a1 1 0 0 1-.87-1.5L12 3z" />
        <line x1="12" y1="9.5" x2="12" y2="14" strokeLinecap="round" />
        <circle cx="12" cy="17.2" r="0.15" fill="currentColor" stroke="none" />
      </svg>
    )
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 9l6 6M15 9l-6 6" />
    </svg>
  )
}

const STATUT_LABEL: Record<string, string> = {
  verrouille: "Verrouillé",
  a_faire: "À faire",
  en_cours: "En cours",
  termine: "Fait",
  non_necessaire: "Non nécessaire",
}

const STATUT_BADGE_CLASS: Record<string, string> = {
  verrouille: "bg-gray-100 text-gray-400",
  a_faire: "bg-amber-50 text-amber-700",
  en_cours: "bg-blue-50 text-blue-700",
  termine: "bg-green-50 text-green-700",
  non_necessaire: "bg-gray-100 text-gray-500",
}

/**
 * Détail d'une étape en popup — ouvert par un clic sur un nœud du graphe
 * (voir RoadmapGraphCanvas → StepNode). Reprend les actions qui étaient avant
 * inline dans StepNode.tsx (cocher fait, déposer une preuve), plus la liste
 * des prérequis, rendue possible par `depends_on` (exposé par le backend
 * depuis cette implémentation — voir roadmap_service._dependencies_map).
 *
 * "Marquer comme non nécessaire" n'est proposé que pour les étapes non
 * bloquantes (`node_snapshot.bloquant === false`) : une étape bloquante ne
 * peut légitimement pas être ignorée (voir seed_roadmap_nodes, colonne
 * `bloquant`).
 */
export default function StepDetailPopup({
  item,
  allItems,
  onClose,
  onToggleDone,
  onUploadProof,
  nameAvailabilityHistory,
  onCheckNameAvailability,
}: StepDetailPopupProps) {
  const [isUpdating, setIsUpdating] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [nomTeste, setNomTeste] = useState("")
  const [isChecking, setIsChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)

  const node = item.node_snapshot
  const isDone = item.statut === "termine"
  const isSkipped = item.statut === "non_necessaire"
  const canMarkSkippable = !node.bloquant && !isSkipped

  const prerequisites = item.depends_on
    .map((depId) => allItems.find((candidate) => candidate.node_id === depId))
    .filter((dep): dep is RoadmapItemRead => dep !== undefined)

  async function runAction(action: () => Promise<void>) {
    setError(null)
    setIsUpdating(true)
    try {
      await action()
    } catch {
      setError("Impossible de mettre à jour cette étape.")
    } finally {
      setIsUpdating(false)
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) handleUpload(file)
    // Permet de réimporter le même fichier deux fois de suite (sinon
    // `onChange` ne se redéclenche pas si la sélection ne change pas) — même
    // pattern que MyProjectPage.handleFileChange / l'ancien StepNode.
    event.target.value = ""
  }

  async function handleUpload(file: File) {
    setError(null)
    setIsUploading(true)
    try {
      await onUploadProof(item.node_id, file)
    } catch {
      setError("Échec de l'envoi de la preuve.")
    } finally {
      setIsUploading(false)
    }
  }

  async function handleCheckName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!nomTeste.trim()) return
    setCheckError(null)
    setIsChecking(true)
    try {
      await onCheckNameAvailability(nomTeste.trim())
      setNomTeste("")
    } catch {
      setCheckError("Échec de la vérification — réessaie dans un instant.")
    } finally {
      setIsChecking(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div
        className="flex max-h-[85vh] w-full max-w-md flex-col gap-4 overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <span
              className={`inline-flex w-fit rounded-full px-2 py-0.5 text-xs font-medium ${
                STATUT_BADGE_CLASS[item.statut] ?? "bg-gray-100 text-gray-500"
              }`}
            >
              {STATUT_LABEL[item.statut] ?? item.statut}
            </span>
            <h2 className="text-base font-semibold text-gray-900">{node.nom}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="shrink-0 rounded-full p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              className="h-5 w-5"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="text-sm text-gray-600">{node.description}</p>

        {node.details_pratiques && (
          <p className="rounded-lg bg-gray-50 p-3 text-xs text-gray-500">{node.details_pratiques}</p>
        )}

        {DOCUMENT_GENERATION_NODE_ROUTES[item.node_id] && (
          <Link
            to={DOCUMENT_GENERATION_NODE_ROUTES[item.node_id].route}
            onClick={onClose}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-center text-sm font-medium text-white transition hover:bg-indigo-700"
          >
            {DOCUMENT_GENERATION_NODE_ROUTES[item.node_id].label}
          </Link>
        )}

        {TEAM_CAPITAL_DATA_NODES.has(item.node_id) && (
          <div className="rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 text-xs text-gray-700">
            Données utilisées : cette étape s'appuie sur ta répartition du capital et des droits de vote.{" "}
            <Link
              to="/entrepreneur/mon-projet/equipe-capital"
              className="font-medium text-indigo-600 underline hover:text-indigo-700"
            >
              Gérer les associés dans « Équipe & capital »
            </Link>
          </div>
        )}

        {item.node_id === NAME_AVAILABILITY_NODE_ID && (
          <div className="flex flex-col gap-2 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3">
            <span className="text-xs font-medium text-gray-700">Vérifier la disponibilité d'un nom</span>
            <form onSubmit={handleCheckName} className="flex items-center gap-2">
              <input
                type="text"
                value={nomTeste}
                onChange={(event) => setNomTeste(event.target.value)}
                placeholder="Nom à tester"
                className="flex-1 rounded-md border border-gray-200 px-2.5 py-1.5 text-xs text-gray-700 focus:border-indigo-400 focus:outline-none"
              />
              <button
                type="submit"
                disabled={isChecking || !nomTeste.trim()}
                className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {isChecking ? "Vérification..." : "Vérifier"}
              </button>
            </form>

            {checkError && <p className="text-xs text-red-600">{checkError}</p>}

            {nameAvailabilityHistory.length > 0 && (
              <div className="flex flex-col gap-1">
                {nameAvailabilityHistory.map((check) => {
                  const verdict = verdictCombinaison(check.statut_denomination, check.statut_marque)
                  return (
                    <div key={check.id} className="flex flex-col gap-1.5 rounded-md bg-white px-2.5 py-2">
                      <span className="text-xs font-medium text-gray-700">{check.nom_teste}</span>

                      {/* Verdict en avant — le détail (badges ci-dessous) reste
                          visible mais secondaire. Voir échange du 2026-09-12 :
                          deux badges bruts obligeaient l'entrepreneur à faire
                          lui-même la synthèse juridique Nom vs Marque. */}
                      <div className={`flex items-center gap-2 rounded-md px-2 py-1.5 ${VERDICT_BG_CLASS[verdict.tone]}`}>
                        <VerdictIcon tone={verdict.tone} />
                        <div className="flex flex-col gap-0.5">
                          <span className={`text-[12px] font-semibold ${VERDICT_TEXT_CLASS[verdict.tone]}`}>
                            {verdict.label}
                          </span>
                          <span className="text-[10px] text-gray-500">{verdict.sub}</span>
                        </div>
                      </div>

                      <div className="flex shrink-0 gap-1">
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                            STATUT_DENOMINATION_CLASS[check.statut_denomination] ?? "bg-gray-100 text-gray-500"
                          }`}
                        >
                          Nom : {STATUT_DENOMINATION_LABEL[check.statut_denomination] ?? check.statut_denomination}
                        </span>
                        <span
                          className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                            STATUT_MARQUE_CLASS[check.statut_marque] ?? "bg-gray-100 text-gray-500"
                          }`}
                        >
                          Marque : {STATUT_MARQUE_LABEL[check.statut_marque] ?? check.statut_marque}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {prerequisites.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-gray-500">Étapes requises</span>
            <div className="flex flex-col gap-1">
              {prerequisites.map((dep) => (
                <div
                  key={dep.node_id}
                  className="flex items-center justify-between gap-2 rounded-md bg-gray-50 px-2.5 py-1.5"
                >
                  <span className="text-xs text-gray-700">{dep.node_snapshot.nom}</span>
                  <span
                    className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                      STATUT_BADGE_CLASS[dep.statut] ?? "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {STATUT_LABEL[dep.statut] ?? dep.statut}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {item.statut === "verrouille" && (
          <p className="text-xs text-amber-600">
            Verrouillée tant que les étapes requises ci-dessus ne sont pas terminées — tu peux quand même la cocher si
            tu l'as déjà faite.
          </p>
        )}

        <div className="flex flex-col gap-2 border-t border-gray-100 pt-3">
          <button
            type="button"
            disabled={isUpdating}
            onClick={() => runAction(() => onToggleDone(item.node_id, isDone ? "a_faire" : "termine"))}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isDone ? "Marquer à faire" : "Marquer comme terminée"}
          </button>

          {canMarkSkippable && (
            <button
              type="button"
              disabled={isUpdating}
              onClick={() => runAction(() => onToggleDone(item.node_id, "non_necessaire"))}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-50"
            >
              Marquer comme non nécessaire
            </button>
          )}

          <div className="flex items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              onChange={handleFileChange}
              className="hidden"
              id={`proof-upload-${item.node_id}`}
            />
            <label
              htmlFor={`proof-upload-${item.node_id}`}
              className={`cursor-pointer text-xs font-medium text-indigo-600 hover:text-indigo-700 ${
                isUploading ? "pointer-events-none opacity-50" : ""
              }`}
            >
              {isUploading ? "Envoi en cours..." : item.proof_document_url ? "Remplacer la preuve" : "Ajouter une preuve"}
            </label>
            {item.proof_document_url && (
              <a
                href={item.proof_document_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-gray-500 underline hover:text-gray-700"
              >
                Voir le document
              </a>
            )}
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  )
}
