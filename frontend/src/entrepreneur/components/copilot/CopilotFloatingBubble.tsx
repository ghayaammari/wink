import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import type { DomaineRedirection, RapportDomaine } from "../../api/copilotApi"
import { useCopilotChat } from "../../hooks/useCopilotChat"

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
  rgpd: "Rapport RGPD (PDF)",
  "ai-act": "Rapport AI Act (PDF)",
  healthtech: "Rapport HealthTech (PDF)",
  fintech: "Rapport FinTech (PDF)",
}

function ICON_SPARKLE({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={className}>
      <path d="M10 2.5l1.6 4.3 4.4 1.6-4.4 1.6L10 14.3l-1.6-4.3-4.4-1.6 4.4-1.6L10 2.5z" />
      <path d="M16 13l.7 1.8L18.5 15.5l-1.8.7L16 18l-.7-1.8-1.8-.7 1.8-.7L16 13z" opacity="0.7" />
    </svg>
  )
}

function ICON_CLOSE() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
      <path d="M5 5l10 10M15 5 5 15" strokeLinecap="round" />
    </svg>
  )
}

function ICON_EXPAND() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="h-4 w-4">
      <path d="M8 4H4v4M12 16h4v-4M4 4l5 5M16 16l-5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

/**
 * Bulle flottante du copilot conformité, visible sur TOUTES les pages
 * entrepreneur (montée dans DashboardLayout, à côté de <Outlet/> -- voir
 * DashboardLayout.tsx) -- en plus de l'entrée dédiée "Copilot" dans la
 * sidebar (CopilotPage.tsx, conversation plein écran). Objectif : pouvoir
 * poser une question au copilot sans quitter la page en cours (ex: pendant
 * le remplissage d'un diagnostic), plutôt que de forcer une navigation.
 *
 * Partage le même CopilotContext (même historique, même conversation
 * active) que CopilotPage.tsx via useCopilotChat() -- ouvrir la bulle puis
 * la page complète (ou l'inverse) montre la même conversation, jamais deux
 * historiques distincts.
 *
 * Volontairement plus simple que CopilotPage.tsx : pas d'édition de
 * message ni de copier (fonctions avancées, gardées pour la vue plein
 * écran) -- ici l'objectif est la question rapide, pas la relecture d'une
 * longue conversation.
 *
 * Masquée sur /entrepreneur/copilot lui-même : la page complète y est déjà
 * affichée, une bulle par-dessus serait redondante.
 */
export default function CopilotFloatingBubble() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const {
    messages,
    draft,
    setDraft,
    isSending,
    error,
    handleSend,
    downloadingDomaine,
    handleDownloadRapport,
    downloadingDocumentRef,
    handleDownloadDocument,
  } = useCopilotChat()
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!isOpen) return
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, isSending, isOpen])

  if (pathname === "/entrepreneur/copilot") return null

  function handleRedirection(domaine: DomaineRedirection) {
    setIsOpen(false)
    navigate(`${DOMAINE_ROUTES[domaine]}?from=copilot`)
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {isOpen && (
        <div className="flex h-[28rem] w-96 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-gray-100 bg-wink-600 px-4 py-3 text-white">
            <div className="flex items-center gap-2">
              <ICON_SPARKLE className="h-4 w-4" />
              <span className="text-sm font-medium">Copilot</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false)
                  navigate("/entrepreneur/copilot")
                }}
                title="Ouvrir en plein écran"
                className="rounded p-1 text-wink-100 hover:bg-white/10 hover:text-white"
              >
                <ICON_EXPAND />
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Fermer"
                className="rounded p-1 text-wink-100 hover:bg-white/10 hover:text-white"
              >
                <ICON_CLOSE />
              </button>
            </div>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3">
            <div className="flex flex-col gap-2.5">
              {messages.map((message, index) => {
                const isUser = message.role === "user"
                return (
                  <div key={index} className={`flex max-w-[88%] gap-2 ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}>
                    {!isUser && (
                      <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-wink-600 text-white">
                        <ICON_SPARKLE className="h-3 w-3" />
                      </div>
                    )}
                    <div className="flex flex-col gap-1">
                      <div
                        className={`flex flex-col gap-2 rounded-lg px-2.5 py-2 text-xs ${
                          isUser ? "bg-wink-600 text-white" : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                        {message.rediriger_vers && (
                          <button
                            type="button"
                            onClick={() => handleRedirection(message.rediriger_vers as DomaineRedirection)}
                            className="w-fit rounded-md bg-white px-2 py-1 text-[11px] font-medium text-wink-700 shadow-sm transition hover:bg-wink-50"
                          >
                            {DOMAINE_LABELS[message.rediriger_vers]} →
                          </button>
                        )}
                        {message.rapport_disponible && (
                          <button
                            type="button"
                            onClick={() => handleDownloadRapport(message.rapport_disponible as RapportDomaine)}
                            disabled={downloadingDomaine === message.rapport_disponible}
                            className="w-fit rounded-md bg-white px-2 py-1 text-[11px] font-medium text-wink-700 shadow-sm transition hover:bg-wink-50 disabled:opacity-50"
                          >
                            {downloadingDomaine === message.rapport_disponible
                              ? "Génération..."
                              : RAPPORT_LABELS[message.rapport_disponible]}
                          </button>
                        )}
                        {message.document_ref && message.titre_document && (
                          <button
                            type="button"
                            onClick={() => handleDownloadDocument(message.document_ref!, message.titre_document!)}
                            disabled={downloadingDocumentRef === message.document_ref}
                            className="w-fit rounded-md bg-white px-2 py-1 text-[11px] font-medium text-wink-700 shadow-sm transition hover:bg-wink-50 disabled:opacity-50"
                          >
                            {downloadingDocumentRef === message.document_ref ? "Génération..." : `${message.titre_document} (PDF)`}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
              {isSending && (
                <div className="mr-auto flex max-w-[88%] items-center gap-2">
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-wink-600 text-white">
                    <ICON_SPARKLE className="h-3 w-3" />
                  </div>
                  <div className="flex items-center gap-1 rounded-lg bg-gray-100 px-2.5 py-2">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400" />
                  </div>
                </div>
              )}
            </div>
          </div>

          {error && <p className="px-3 pb-1.5 text-[11px] text-red-600">{error}</p>}

          <div className="border-t border-gray-100 p-2.5">
            <div className="flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2 py-1 shadow-sm transition focus-within:border-wink-300 focus-within:ring-2 focus-within:ring-wink-100">
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
                disabled={isSending}
                placeholder="Pose ta question..."
                className="flex-1 bg-transparent px-1.5 py-1 text-xs focus:outline-none disabled:opacity-50"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={isSending || !draft.trim()}
                className="rounded-full bg-wink-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-wink-700 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Envoyer
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        title={isOpen ? "Fermer le copilot" : "Ouvrir le copilot (création d'entreprise, conformité...)"}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-wink-600 text-white shadow-lg transition hover:scale-105 hover:bg-wink-700"
      >
        {isOpen ? <ICON_CLOSE /> : <ICON_SPARKLE className="h-6 w-6" />}
      </button>
    </div>
  )
}
