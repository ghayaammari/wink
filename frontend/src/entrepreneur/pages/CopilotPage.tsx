import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import type { DomaineRedirection, RapportDomaine } from "../api/copilotApi"
import { useCopilotChat } from "../hooks/useCopilotChat"

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

function ICON_SPARKLE({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className}>
      <path d="M10 2.5l1.6 4.3 4.4 1.6-4.4 1.6L10 14.3l-1.6-4.3-4.4-1.6 4.4-1.6L10 2.5z" />
      <path d="M16 13l.7 1.8L18.5 15.5l-1.8.7L16 18l-.7-1.8-1.8-.7 1.8-.7L16 13z" opacity="0.7" />
    </svg>
  )
}

const SUGGESTIONS_COPILOT = [
  "Quelle forme juridique choisir pour notre startup ?",
  "Quelles données personnelles collectons-nous et faut-il un DPO ?",
  "Des chercheurs recommandés sur mon dernier besoin déposé ?",
]

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
  const navigate = useNavigate()
  const {
    projectId,
    messages,
    draft,
    setDraft,
    isSending,
    error,
    envoyerConversation,
    handleSend,
    downloadingDomaine,
    downloadError,
    handleDownloadRapport,
    downloadingDocumentRef,
    handleDownloadDocument,
  } = useCopilotChat()
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editDraft, setEditDraft] = useState("")
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, isSending])

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

  return (
    <div className="flex h-[calc(100vh_-_4rem)] flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
          <ICON_SPARKLE className="h-5 w-5" />
        </div>
        <div className="flex flex-col gap-0.5">
          <h1 className="text-xl font-semibold text-gray-900">Copilot</h1>
          <p className="text-sm text-gray-500">
            Création d'entreprise (statuts, immatriculation, forme juridique...) ou conformité (RGPD, AI Act,
            secteurs réglementés) — le copilot peut aussi te rediriger vers le bon diagnostic.
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded-lg border border-gray-200 bg-white">
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-wink-50 text-wink-600">
                <ICON_SPARKLE className="h-6 w-6" />
              </div>
              <div className="flex flex-col gap-1">
                <p className="text-sm font-medium text-gray-700">Comment puis-je t'aider ?</p>
                <p className="text-xs text-gray-400">
                  Création d'entreprise ou conformité (RGPD, AI Act, secteurs réglementés) — pose une question ou
                  décris ta situation.
                </p>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS_COPILOT.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setDraft(suggestion)}
                    className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 transition hover:border-wink-300 hover:bg-wink-50 hover:text-wink-700"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
          <div className="flex flex-col gap-3">
            {messages.map((message, index) => {
              const isUser = message.role === "user"
              const isEditing = editingIndex === index

              if (isUser && isEditing) {
                return (
                  <div key={index} className="ml-auto flex w-[80%] flex-col gap-2 rounded-lg bg-wink-50 p-2">
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
                      className="w-full resize-none rounded-md border border-wink-200 bg-white p-2 text-sm focus:border-wink-400 focus:outline-none"
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
                        className="rounded-md bg-wink-600 px-2 py-1 text-xs font-medium text-white hover:bg-wink-700 disabled:opacity-50"
                      >
                        Renvoyer
                      </button>
                    </div>
                  </div>
                )
              }

              return (
                <div key={index} className={`group flex max-w-[85%] gap-2 ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}>
                  {!isUser && (
                    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-wink-600 text-white">
                      <ICON_SPARKLE className="h-3.5 w-3.5" />
                    </div>
                  )}
                <div className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}>
                  <div
                    className={`flex flex-col gap-2 rounded-lg px-3 py-2 text-sm ${
                      isUser ? "bg-wink-600 text-white" : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.rediriger_vers && (
                      <button
                        type="button"
                        onClick={() => handleRedirection(message.rediriger_vers as DomaineRedirection)}
                        className="w-fit rounded-md bg-white px-3 py-1.5 text-xs font-medium text-wink-700 shadow-sm transition hover:bg-wink-50"
                      >
                        {DOMAINE_LABELS[message.rediriger_vers]} →
                      </button>
                    )}
                    {message.rapport_disponible && (
                      <button
                        type="button"
                        onClick={() => handleDownloadRapport(message.rapport_disponible as RapportDomaine)}
                        disabled={downloadingDomaine === message.rapport_disponible}
                        className="w-fit rounded-md bg-white px-3 py-1.5 text-xs font-medium text-wink-700 shadow-sm transition hover:bg-wink-50 disabled:opacity-50"
                      >
                        {downloadingDomaine === message.rapport_disponible
                          ? "Génération du rapport..."
                          : RAPPORT_LABELS[message.rapport_disponible]}
                      </button>
                    )}
                    {message.document_ref && message.titre_document && (
                      <button
                        type="button"
                        onClick={() => handleDownloadDocument(message.document_ref!, message.titre_document!)}
                        disabled={downloadingDocumentRef === message.document_ref}
                        className="w-fit rounded-md bg-white px-3 py-1.5 text-xs font-medium text-wink-700 shadow-sm transition hover:bg-wink-50 disabled:opacity-50"
                      >
                        {downloadingDocumentRef === message.document_ref
                          ? "Génération du document..."
                          : `Télécharger "${message.titre_document}" (PDF)`}
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
                </div>
              )
            })}
            {isSending && (
              <div className="mr-auto flex max-w-[85%] items-center gap-2">
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-wink-600 text-white">
                  <ICON_SPARKLE className="h-3.5 w-3.5" />
                </div>
                <div className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-2.5">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
                </div>
              </div>
            )}
          </div>
          )}
        </div>

        {(error || downloadError) && <p className="px-4 pb-2 text-xs text-red-600">{error ?? downloadError}</p>}

        <div className="border-t border-gray-200 p-3">
          <div className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-2 py-1.5 shadow-sm transition focus-within:border-wink-300 focus-within:ring-2 focus-within:ring-wink-100">
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
              className="flex-1 bg-transparent px-2 py-1.5 text-sm focus:outline-none disabled:opacity-50"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={isSending || !draft.trim() || !projectId}
              className="rounded-full bg-wink-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-wink-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Envoyer
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
