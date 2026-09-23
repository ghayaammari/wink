import { useNavigate } from "react-router-dom"
import { useCopilot } from "../../context/CopilotContext"

/**
 * Contenu deroulant sous l'entree "Copilot" de la Sidebar (voir le slot
 * `renderChildren` dans shared/components/Sidebar.tsx) : bouton "Nouvelle
 * conversation" + historique des conversations. Rendu directement dans la
 * navigation globale (pas dans CopilotPage.tsx) pour rester visible partout
 * ou le copilot est accessible, pas seulement sur sa propre page -- d'ou le
 * useNavigate() pour rejoindre /entrepreneur/copilot au clic si on est
 * ailleurs dans l'app.
 */
export default function CopilotSidebarConversations() {
  const navigate = useNavigate()
  const {
    conversations,
    isLoadingConversations,
    conversationsError,
    activeConversationId,
    createNewConversation,
    selectConversation,
  } = useCopilot()

  async function handleNewConversation() {
    await createNewConversation()
    navigate("/entrepreneur/copilot")
  }

  async function handleSelect(conversationId: string) {
    await selectConversation(conversationId)
    navigate("/entrepreneur/copilot")
  }

  return (
    <div className="ml-4 flex flex-col gap-1 border-l border-gray-100 pl-4">
      <button
        type="button"
        onClick={handleNewConversation}
        className="rounded-lg px-3 py-1.5 text-left text-sm text-indigo-600 transition hover:bg-indigo-50"
      >
        + Nouvelle conversation
      </button>

      {isLoadingConversations && (
        <p className="px-3 py-1 text-xs text-gray-400">Chargement...</p>
      )}

      {conversationsError && (
        <p className="px-3 py-1 text-xs text-red-500">{conversationsError}</p>
      )}

      {!isLoadingConversations && conversations.length === 0 && !conversationsError && (
        <p className="px-3 py-1 text-xs text-gray-400">Aucune conversation.</p>
      )}

      {conversations.map((conversation) => (
        <button
          key={conversation.id}
          type="button"
          onClick={() => handleSelect(conversation.id)}
          className={`truncate rounded-lg px-3 py-1.5 text-left text-sm transition ${
            conversation.id === activeConversationId
              ? "bg-indigo-50 font-medium text-indigo-700"
              : "text-gray-500 hover:bg-gray-50 hover:text-gray-900"
          }`}
          title={conversation.titre}
        >
          {conversation.titre}
        </button>
      ))}
    </div>
  )
}
