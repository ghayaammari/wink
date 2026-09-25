import type { PacteFondateurCopilotSource } from "./pacteFondateurCopilotApi"

export interface CopilotDisplayMessage {
  role: "user" | "assistant"
  content: string
  sources?: PacteFondateurCopilotSource[]
}

/**
 * Rendu d'un seul echange (question OU reponse) dans la bulle -- un fichier,
 * une responsabilite : juste l'affichage, aucun state ni appel API ici (voir
 * PacteFondateurCopilotWidget.tsx pour l'orchestration).
 */
export default function PacteFondateurCopilotMessage({ role, content, sources }: CopilotDisplayMessage) {
  const isUser = role === "user"

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-800"
        }`}
      >
        {content}
        {/* Sources affichees seulement cote reponse, et seulement si le
            backend en a trouve -- recherche_generale_tool.py renvoie une
            liste vide + note explicite plutot que d'inventer une source. */}
        {!isUser && sources && sources.length > 0 && (
          <ul className="mt-2 space-y-1 border-t border-slate-200 pt-2 text-xs text-slate-500">
            {sources.map((source, index) => (
              <li key={`${source.source_type}-${source.source_id}-${index}`}>
                {source.citation ?? `${source.source_type} (source non resolue)`}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
