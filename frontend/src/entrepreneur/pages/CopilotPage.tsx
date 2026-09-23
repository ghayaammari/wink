import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { downloadAiActReport } from "../api/aiActApi"
import { sendCopilotMessage, type DomaineRedirection, type RapportDomaine } from "../api/copilotApi"
import { getMyProject } from "../api/projectApi"
import { downloadRgpdReport } from "../api/rgpdApi"
import { downloadFintechGapAnalysisReport, downloadHealthtechGapAnalysisReport } from "../api/sectorApi"
import { useCopilot, type CopilotDisplayMessage } from "../context/CopilotContext"

const DOMAINE_ROUTES: Record<DomaineRedirection, string> = {
  rgpd: "/entrepreneur/conformite/rgpd",
  "ai-act": "/entrepreneur/conformite/ai-act",
  secteur: "/entrepreneur/conformite/secteur",
}

const DOMAINE_LABELS: Record<DomaineRedirection, string> = {
  rgpd: "Ouvrir le diagnostic RGPD",
  "ai-act": "Ouvrir le diagnostic AI Act",
  secteur: "Ouvrir la conformité sectorielle",
}

const RAPPORT_DOWNLOADERS: Record<RapportDomaine, (accessToken: string, projectId: string) => Promise<void>> = {
  rgpd: downloadRgpdReport,
  "ai-act": downloadAiActReport,
  healthtech: downloadHealthtechGapAnalysisReport,
  fintech: downloadFintechGapAnalysisReport,
}

const RAPPORT_LABELS: Record<RapportDomaine, string> = {
  rgpd: "Télécharger le rapport RGPD (PDF)",
  "ai-act": "Télécharger le rapport AI Act (PDF)",
  healthtech: "Télécharger le rapport HealthTech (PDF)",
  fintech: "Télécharger le rapport FinTech (PDF)",
}

function ICON_COPY() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5">
      <rect x="7" y="7" width="9" height="9" rx="1.5" />
      <path d="M4.5 12.5V5A1.5 1.5 0 0 1 6 3.5h7.5" strokeLinecap="round" />
    </svg>
  )
}

function ICON_EDIT() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5">
      <path d="M13.5 3.5 16.5 6.5 6.5 16.5H3.5V13.5Z" strokeLinejoin="round" />
    </svg>
  )
}

function ICON_CHECK() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-3.5 w-3.5">
      <path d="M4 10.5 8 14.5 16 5.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * Copilot conformité — entrée de premier niveau dans la sidebar
 * entrepreneur, au même titre que "Plan d'action" ou "Conformité" (voir
 * App.tsx, ENTREPRENEUR_NAV_ITEMS). La liste des conversations et le bouton
 * "Nouvelle conversation" vivent maintenant dans la Sidebar globale (voir
 * CopilotSidebarConversations.tsx, monté via le slot `renderChildren` de
 * l'entrée "Copilot") : cette page ne rend plus qu'une seule colonne, la
 * zone de chat de la conversation active.
 *
 * L'état (conversation active, messages affichés, liste des conversations)
 * vit dans CopilotContext (monté une fois dans DashboardLayout, partagé
 * avec la Sidebar), pas ici : il doit survivre à un aller-retour vers un
 * diagnostic (redirection puis bouton "Terminer") et rester visible dans la
 * Sidebar même quand cette page n'est pas montée.
 *
 * Deux actions sur un message utilisateur, au survol (comme l'interface
 * Claude) : copier le texte, ou l'éditer puis le renvoyer — ce second cas
 * tronque la conversation à ce point (message édité + tout ce qui suit
 * disparaît définitivement, y compris côté backend, voir
 * copilotApi.ts::sendCopilotMessage) avant d'envoyer la version modifiée.
 */
export default function CopilotPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()
  const { messages, appendMessage, setMessages, ensureActiveConversation, refreshConversations } = useCopilot()
  const [projectId, setProjectId] = useState<string | null>(null)
  const [draft, setDraft] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState("")
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const [downloadingDomaine, setDownloadingDomaine] = useState<RapportDomaine | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!accessToken || projectId) return
    getMyProject(accessToken)
      .then((project) => setProjectId(project?.id ?? null))
      .catch(() => setError("Impossible de charger ton projet."))
  }, [accessToken, projectId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, isSending])

  // Coeur partage par l'envoi normal et l'edition+renvoi : `historiqueLocal`
  // est ce qu'on affiche immediatement (optimiste), `tronquerA` dit au
  // backend jusqu'ou garder l'historique deja persiste avant d'y ajouter ce
  // nouveau message (voir sendCopilotMessage).
  async function envoyerConversation(historiqueLocal: CopilotDisplayMessage[], contenu: string, tronquerA?: number) {
    if (!accessToken || !projectId || isSending) return
    setMessages([...historiqueLocal, { role: "user", content: contenu }])
    setIsSending(true)
    setError(null)

    try {
      const conversationId = await ensureActiveConversation()
      if (!conversationId) throw new Error("Aucune conversation active.")
      const result = await sendCopilotMessage(accessToken, projectId, conversationId, contenu, tronquerA)
      appendMessage({
        role: "assistant",
        content: result.reponse,
        rediriger_vers: result.rediriger_vers,
        ancrage_verifie: result.ancrage_verifie,
      })
      // Le premier message peut avoir donne son titre a la conversation
      // cote backend (voir _generer_titre) -- rafraichit la liste partagee
      // (Sidebar) pour qu'elle ne reste pas bloquee sur "Nouvelle conversation".
      await refreshConversations()
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "Le copilot n'a pas pu répondre, réessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setIsSending(false)
    }
  }

  async function handleSend() {
    const content = draft.trim()
    if (!content) return
    setDraft("")
    await envoyerConversation(messages, content)
  }

  async function handleEditResend(index: number) {
    const content = editDraft.trim()
    if (!content) return
    setEditingIndex(null)
    // Tronque a ce message (lui et tout ce qui suit disparaissent, y
    // compris cote backend via tronquerA) avant de renvoyer la version
    // editee -- comportement d'edition de Claude.
    await envoyerConversation(messages.slice(0, index), content, index)
  }

  async function handleCopy(index: number, content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex((current) => (current === index ? null : current)), 1500)
    } catch {
      // Presse-papiers indisponible -- pas bloquant, on ignore le retour visuel.
    }
  }

  function handleRedirection(domaine: DomaineRedirection) {
    navigate(`${DOMAINE_ROUTES[domaine]}?from=copilot`)
  }

  async function handleDownloadRapport(domaine: RapportDomaine) {
    if (!accessToken || !projectId || downloadingDomaine) return
    setDownloadingDomaine(domaine)
    setDownloadError(null)
    try {
      await RAPPORT_DOWNLOADERS[domaine](accessToken, projectId)
    } catch {
      setDownloadError("Le téléchargement du rapport a échoué, réessaie dans quelques instants.")
    } finally {
      setDownloadingDomaine(null)
    }
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Copilot conformité</h1>
        <p className="text-sm text-gray-500">
          Pose tes questions sur le RGPD, l'AI Act ou la conformité sectorielle — le copilot peut aussi te rediriger
          vers le bon diagnostic.
        </p>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
          <div className="flex flex-col gap-3">
            {messages.map((message, index) => {
              const isUser = message.role === "user"
              const isEditing = editingIndex === index

              if (isUser && isEditing) {
                return (
                  <div key={index} className="ml-auto flex w-[80%] flex-col gap-2 rounded-lg bg-indigo-50 p-2">
                    <textarea
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault()
                          handleEditResend(index)
                        }
                        if (e.key === "Escape") setEditingIndex(null)
                      }}
                      autoFocus
                      rows={2}
                      className="w-full resize-none rounded-md border border-indigo-200 bg-white p-2 text-sm focus:border-indigo-400 focus:outline-none"
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setEditingIndex(null)}
                        className="rounded-md px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100"
                      >
                        Annuler
                      </button>
                      <button
                        type="button"
                        onClick={() => handleEditResend(index)}
                        disabled={!editDraft.trim() || isSending}
                        className="rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                      >
                        Renvoyer
                      </button>
                    </div>
                  </div>
                )
              }

              return (
                <div
                  key={index}
                  className={`group flex max-w-[80%] flex-col gap-1 ${isUser ? "ml-auto items-end" : "mr-auto items-start"}`}
                >
                  <div
                    className={`flex flex-col gap-2 rounded-lg px-3 py-2 text-sm ${
                      isUser ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.rediriger_vers && (
                      <button
                        type="button"
                        onClick={() => handleRedirection(message.rediriger_vers as DomaineRedirection)}
                        className="w-fit rounded-md bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm transition hover:bg-indigo-50"
                      >
                        {DOMAINE_LABELS[message.rediriger_vers]} →
                      </button>
                    )}
                    {message.rapport_disponible && (
                      <button
                        type="button"
                        onClick={() => handleDownloadRapport(message.rapport_disponible as RapportDomaine)}
                        disabled={downloadingDomaine === message.rapport_disponible}
                        className="w-fit rounded-md bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm transition hover:bg-indigo-50 disabled:opacity-50"
                      >
                        {downloadingDomaine === message.rapport_disponible
                          ? "Génération du rapport..."
                          : RAPPORT_LABELS[message.rapport_disponible]}
                      </button>
                    )}
                  </div>
                  {!isUser && message.ancrage_verifie !== undefined && message.ancrage_verifie !== null && (
                    <p
                      className={`px-1 text-[11px] ${
                        message.ancrage_verifie ? "text-emerald-600" : "text-amber-600"
                      }`}
                    >
                      {message.ancrage_verifie
                        ? "✓ Réponse vérifiée sur le corpus réglementaire"
                        : "⚠ Certaines affirmations ne sont pas confirmées par le corpus — à vérifier"}
                    </p>
                  )}
                  {isUser && (
                    <div className="flex gap-1 opacity-0 transition group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => handleCopy(index, message.content)}
                        title="Copier"
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {copiedIndex === index ? <ICON_CHECK /> : <ICON_COPY />}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingIndex(index)
                          setEditDraft(message.content)
                        }}
                        title="Modifier et renvoyer"
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        <ICON_EDIT />
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
            {isSending && <p className="text-xs text-gray-400">Le copilot réfléchit...</p>}
          </div>
        </div>

        {(error || downloadError) && <p className="px-4 pb-2 text-xs text-red-600">{error ?? downloadError}</p>}

        <div className="flex items-center gap-2 border-t border-gray-200 p-3">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            disabled={isSending || !projectId}
            placeholder="Pose ta question..."
            className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending || !draft.trim() || !projectId}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            Envoyer
          </button>
        </div>
      </div>
    </div>
  )
}
