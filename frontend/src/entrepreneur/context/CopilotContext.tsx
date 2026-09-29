import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { useAuth } from "../../shared/context/AuthContext"
import {
  createConversation,
  getConversation,
  listConversations,
  type CopilotConversationSummary,
  type CopilotMessage,
  type RapportDomaine,
} from "../api/copilotApi"
import { getMyProject } from "../api/projectApi"

export type CopilotDisplayMessage = CopilotMessage

export const MESSAGE_ACCUEIL: CopilotDisplayMessage = {
  role: "assistant",
  content:
    "Bonjour, je suis le copilot de Wink. Pose-moi une question sur la création de ton entreprise (statuts, immatriculation, forme juridique...), ta conformité (RGPD, AI Act, secteurs réglementés) ou l'état de tes recommandations de matching — je peux aussi te rediriger directement vers le bon diagnostic si tu veux le lancer.",
}

interface CopilotContextValue {
  projectId: string | null
  // Liste des conversations du projet -- affichee a la fois dans la barre
  // laterale de l'app (sous l'entree "Copilot", voir
  // CopilotSidebarConversations.tsx) et potentiellement ailleurs -- centralisee
  // ici plutot que chargee separement par chaque composant, pour que creer/
  // selectionner une conversation dans un endroit se reflete partout.
  conversations: CopilotConversationSummary[]
  isLoadingConversations: boolean
  conversationsError: string | null
  activeConversationId: string | null
  messages: CopilotDisplayMessage[]
  setMessages: (messages: CopilotDisplayMessage[]) => void
  appendMessage: (message: CopilotDisplayMessage) => void
  // Cree une conversation, l'ajoute en tete de liste et la selectionne --
  // utilise aussi bien par le bouton "Nouvelle conversation" (sidebar) que
  // par l'envoi du tout premier message d'une session (creation a la volee,
  // voir CopilotPage.tsx).
  createNewConversation: () => Promise<string | null>
  selectConversation: (conversationId: string) => Promise<void>
  // Renvoie l'id de la conversation active, ou en cree une si aucune ne
  // l'est encore -- evite d'imposer un clic explicite sur "Nouvelle
  // conversation" avant de pouvoir simplement parler au copilot.
  ensureActiveConversation: () => Promise<string | null>
  refreshConversations: () => Promise<void>
  // Utilise par les pages de diagnostic quand l'entrepreneur clique
  // "Terminer" (voir RgpdDiagnosticPage.tsx/AiActDiagnosticPage.tsx/
  // SectorDiagnosticPage.tsx) : ajoute un message de confirmation LOCAL
  // (jamais envoye au backend, contrairement aux messages de la conversation).
  addAssistantMessage: (content: string, rapportDisponible?: RapportDomaine) => void
}

const CopilotContext = createContext<CopilotContextValue | null>(null)

/**
 * Etat + logique de donnees du copilot conformite, partages entre
 * CopilotPage.tsx (la page de chat) et CopilotSidebarConversations.tsx
 * (l'historique déroulant sous "Copilot" dans la sidebar de l'app) --
 * centralisé ici pour que les deux restent de purs composants d'affichage,
 * sans dupliquer les appels API. Monte une seule fois dans DashboardLayout
 * (showCopilot), donc survit a toute navigation entre pages entrepreneur.
 *
 * Limite connue (V1 des conversations, 20/09/2026) : le message ajoute par
 * addAssistantMessage (note "Terminer" + bouton de telechargement) reste
 * purement local, jamais persiste dans la conversation cote backend --
 * disparait si on quitte cette conversation puis qu'on y revient.
 */
export function CopilotProvider({ children }: { children: ReactNode }) {
  const { accessToken } = useAuth()
  const [projectId, setProjectId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<CopilotConversationSummary[]>([])
  const [isLoadingConversations, setIsLoadingConversations] = useState(false)
  const [conversationsError, setConversationsError] = useState<string | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<CopilotDisplayMessage[]>([MESSAGE_ACCUEIL])

  useEffect(() => {
    if (!accessToken || projectId) return
    getMyProject(accessToken)
      .then((project) => setProjectId(project?.id ?? null))
      .catch(() => setConversationsError("Impossible de charger ton projet."))
  }, [accessToken, projectId])

  async function refreshConversations() {
    if (!accessToken || !projectId) return
    setIsLoadingConversations(true)
    setConversationsError(null)
    try {
      const list = await listConversations(accessToken, projectId)
      setConversations(list)
    } catch {
      setConversationsError("Impossible de charger tes conversations.")
    } finally {
      setIsLoadingConversations(false)
    }
  }

  useEffect(() => {
    if (accessToken && projectId) refreshConversations()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de projet
  }, [accessToken, projectId])

  async function selectConversation(conversationId: string) {
    if (!accessToken || !projectId) return
    setConversationsError(null)
    try {
      const detail = await getConversation(accessToken, projectId, conversationId)
      setActiveConversationId(conversationId)
      setMessages(detail.messages.length > 0 ? detail.messages : [MESSAGE_ACCUEIL])
    } catch {
      setConversationsError("Impossible de charger cette conversation.")
    }
  }

  // Cree l'enregistrement de conversation cote backend et met a jour la
  // liste/l'id actif, SANS toucher a `messages` -- utilise par les deux
  // fonctions publiques ci-dessous, qui gerent chacune differemment
  // l'affichage local (voir leurs commentaires).
  async function _creerConversationBackend(): Promise<string | null> {
    if (!accessToken || !projectId) return null
    try {
      const conversation = await createConversation(accessToken, projectId)
      setConversations((current) => [conversation, ...current])
      setActiveConversationId(conversation.id)
      return conversation.id
    } catch {
      setConversationsError("Impossible de créer une nouvelle conversation.")
      return null
    }
  }

  // Bouton explicite "Nouvelle conversation" (sidebar) : l'utilisateur
  // quitte volontairement la conversation courante, donc on reinitialise
  // l'affichage au message d'accueil.
  async function createNewConversation(): Promise<string | null> {
    const conversationId = await _creerConversationBackend()
    if (conversationId) setMessages([MESSAGE_ACCUEIL])
    return conversationId
  }

  // Utilise en interne lors de l'envoi du tout premier message d'une
  // session (creation a la volee, voir CopilotPage.tsx::envoyerConversation)
  // : NE DOIT PAS reinitialiser `messages`, qui contient deja a cet instant
  // le message utilisateur ajoute de maniere optimiste juste avant cet
  // appel -- un reset ici l'effacerait silencieusement (bug corrige le
  // 21/09/2026 : la question de l'utilisateur disparaissait de l'affichage).
  async function ensureActiveConversation(): Promise<string | null> {
    if (activeConversationId) return activeConversationId
    return _creerConversationBackend()
  }

  function addAssistantMessage(content: string, rapportDisponible?: RapportDomaine) {
    setMessages((current) => [...current, { role: "assistant", content, rapport_disponible: rapportDisponible }])
  }

  return (
    <CopilotContext.Provider
      value={{
        projectId,
        conversations,
        isLoadingConversations,
        conversationsError,
        activeConversationId,
        messages,
        setMessages,
        appendMessage: (message) => setMessages((current) => [...current, message]),
        createNewConversation,
        selectConversation,
        ensureActiveConversation,
        refreshConversations,
        addAssistantMessage,
      }}
    >
      {children}
    </CopilotContext.Provider>
  )
}

export function useCopilot(): CopilotContextValue {
  const ctx = useContext(CopilotContext)
  if (!ctx) {
    throw new Error("useCopilot doit etre utilise a l'interieur de CopilotProvider.")
  }
  return ctx
}
