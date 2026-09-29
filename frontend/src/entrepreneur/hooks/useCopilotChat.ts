import { useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { downloadAiActReport } from "../api/aiActApi"
import { downloadCopilotDocument, sendCopilotMessage, type RapportDomaine } from "../api/copilotApi"
import { downloadRgpdReport } from "../api/rgpdApi"
import { downloadFintechGapAnalysisReport, downloadHealthtechGapAnalysisReport } from "../api/sectorApi"
import { useCopilot, type CopilotDisplayMessage } from "../context/CopilotContext"

const RAPPORT_DOWNLOADERS: Record<RapportDomaine, (accessToken: string, projectId: string) => Promise<void>> = {
  rgpd: downloadRgpdReport,
  "ai-act": downloadAiActReport,
  healthtech: downloadHealthtechGapAnalysisReport,
  fintech: downloadFintechGapAnalysisReport,
}

/**
 * Logique d'envoi de message + telechargement de rapport, partagee entre
 * CopilotPage.tsx (page complete, avec edition de message en plus) et
 * CopilotFloatingBubble.tsx (bulle flottante, plus simple) -- extrait de
 * CopilotPage.tsx pour eviter de dupliquer l'appel sendCopilotMessage et sa
 * gestion d'erreur a deux endroits (voir CopilotFloatingBubble.tsx).
 *
 * `projectId` vient de CopilotContext (deja charge une fois par
 * CopilotProvider, voir DashboardLayout.tsx) -- ce hook ne refait plus son
 * propre appel getMyProject comme le faisait CopilotPage.tsx avant cette
 * extraction (2 appels reseau pour la meme donnee, corrige au passage).
 */
export function useCopilotChat() {
  const { accessToken } = useAuth()
  const {
    projectId,
    messages,
    appendMessage,
    setMessages,
    ensureActiveConversation,
    refreshConversations,
    activeConversationId,
  } = useCopilot()
  const [draft, setDraft] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [downloadingDomaine, setDownloadingDomaine] = useState<RapportDomaine | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  // Jeton du document en cours de telechargement (distinct de
  // downloadingDomaine : un document libre du copilot n'a pas de domaine
  // fixe, voir CopilotMessage.document_ref).
  const [downloadingDocumentRef, setDownloadingDocumentRef] = useState<string | null>(null)

  // Coeur partage par l'envoi normal et l'edition+renvoi (CopilotPage.tsx
  // uniquement, la bulle n'edite pas de message) : `historiqueLocal` est ce
  // qu'on affiche immediatement (optimiste), `tronquerA` dit au backend
  // jusqu'ou garder l'historique deja persiste avant d'y ajouter ce nouveau
  // message (voir sendCopilotMessage).
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
        titre_document: result.titre_document,
        document_ref: result.document_ref,
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

  async function handleDownloadDocument(documentRef: string, titreDocument: string) {
    if (!accessToken || !projectId || !activeConversationId || downloadingDocumentRef) return
    setDownloadingDocumentRef(documentRef)
    setDownloadError(null)
    try {
      await downloadCopilotDocument(accessToken, projectId, activeConversationId, documentRef, titreDocument)
    } catch {
      setDownloadError("Le téléchargement du document a échoué, réessaie dans quelques instants.")
    } finally {
      setDownloadingDocumentRef(null)
    }
  }

  return {
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
  }
}
