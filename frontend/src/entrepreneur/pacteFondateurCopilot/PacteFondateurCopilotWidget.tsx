import { useEffect, useRef, useState, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  getHistorique,
  poserQuestion,
  pousserExplicationAutomatique,
  type PacteFondateurCopilotSource,
} from "./pacteFondateurCopilotApi"
import PacteFondateurCopilotMessage, { type CopilotDisplayMessage } from "./PacteFondateurCopilotMessage"

export interface CopilotClauseVariable {
  /** Nom technique (ClauseVariable.nom cote backend) -- c'est CE nom que le
   * tool expliquer_impact_variable attend en parametre, jamais le libelle. */
  nom: string
  /** Libelle humain affiche a l'utilisateur (ex. "Duree du delai de
   * preemption"). */
  libelle: string
}

export interface CopilotClauseContexte {
  code_clause: string
  titre_clause: string
  /** Variables de la clause en cours -- utilisees pour generer des
   * suggestions rapides "Quel est l'impact de [variable] ?". Optionnel :
   * les clauses sans variable (ex. mentions obligatoires) n'en ont
   * simplement pas. */
  variables?: CopilotClauseVariable[]
  /** AJOUT (27/09/2026, service 1.1.15) -- necessaires pour
   * pousserExplicationAutomatique() : quelle section/document_type expliquer
   * automatiquement des que cette clause devient le contexte courant. */
  documentType: string
  codeSection: string
}

interface PacteFondateurCopilotWidgetProps {
  projectId: string
  /** Clause actuellement affichee dans le questionnaire (section en cours),
   * ou null hors d'une section (ecran d'accueil, selection des fondateurs,
   * finalisation). Recalculee par le parent a chaque changement de section
   * -- voir PacteFondateursV2Page.tsx. */
  clauseContexte: CopilotClauseContexte | null
}

const MAX_SUGGESTIONS_VARIABLES = 2

/**
 * Bulle de copilot persistante du pacte de fondateurs (service 1.1.13,
 * categorie 3) -- portee validee : reponses libres sur le pacte en general
 * + explication de la clause affichee + impact d'une variable, historique
 * reaffiche a la reouverture (persistant en base, pas seulement en memoire).
 *
 * Montee une seule fois au niveau de PacteFondateursV2Page (au-dessus des
 * phases welcome/founders_selection/in_progress/finalized) pour ne PAS etre
 * demontee/remontee a chaque changement de phase -- sinon l'etat
 * ouvert/ferme et le scroll de la conversation se reinitialiseraient a
 * chaque transition, alors que la conversation, elle, reste la meme
 * (persistee cote serveur, une seule par projet).
 *
 * SCOPE VOLONTAIRE (25/09/2026) : v2 uniquement, pas la page pacte-fondateurs
 * v1 (ancienne version amenee a etre retiree) -- decision actee avec
 * l'utilisateur plutot que dupliquer l'integration dans un ecran qui va
 * disparaitre.
 *
 * SEUL MECANISME D'EXPLICATION (27/09/2026, service 1.1.15, consolidation) :
 * ce widget est desormais le point d'entree UNIQUE pour toute explication IA
 * du pacte -- avant lui s'ajoutaient une icone sur chaque titre de clause et
 * un historique dedie des sections deja redigees, retires suite a un retour
 * "jury" (3 mecanismes concurrents pour la meme action). Deux chemins
 * cohabitent ICI, dans la MEME conversation persistee :
 * - automatique : `pousserExplicationAutomatique()`, declenchee des que
 *   `clauseContexte` change (nouvelle section affichee) -- un appel LLM
 *   dedie (agents/contract_agent/clause_explanation_service.py), pas le RAG.
 * - a la demande : la suggestion "Explique-moi cette clause" (voir
 *   buildSuggestions ci-dessous), qui passe par poserQuestion()/le RAG de
 *   l'agent copilot (avec citations) -- masquee une fois l'explication
 *   automatique deja recue pour cette clause, pour ne pas demander deux fois
 *   la meme chose.
 */
export default function PacteFondateurCopilotWidget({ projectId, clauseContexte }: PacteFondateurCopilotWidgetProps) {
  const { accessToken } = useAuth()

  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<CopilotDisplayMessage[]>([])
  const [hasLoadedHistory, setHasLoadedHistory] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [inputValue, setInputValue] = useState("")
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // BUG CORRIGE (25/09/2026, signale par l'utilisateur) : les suggestions
  // etaient masquees des le premier message envoye, POUR TOUJOURS (gate sur
  // messages.length === 0, global a toute la conversation persistante du
  // projet) -- donc plus jamais revues en naviguant vers une nouvelle
  // clause/section, alors que ce sont precisement les suggestions de CETTE
  // nouvelle clause qui redeviennent utiles. Remplace par un suivi "derniere
  // clause pour laquelle l'utilisateur a deja envoye un message" : les
  // suggestions se re-affichent des que `clauseContexte.code_clause` change.
  const [suggestionsDismissedForClause, setSuggestionsDismissedForClause] = useState<string | null>(null)

  // Service 1.1.15 (27/09/2026) -- clauses pour lesquelles l'explication
  // automatique a deja ete recue (que le widget soit ouvert ou non) : sert a
  // 1) ne pas repousser deux fois la meme clause dans la meme session
  // (idempotence cote frontend, en plus de celle du backend) et 2) masquer
  // la suggestion "Explique-moi cette clause", devenue redondante.
  const [autoExplainedClauses, setAutoExplainedClauses] = useState<Set<string>>(new Set())
  const [hasUnseenAutoExplanation, setHasUnseenAutoExplanation] = useState(false)

  const scrollAnchorRef = useRef<HTMLDivElement | null>(null)

  // Historique charge une seule fois, a la premiere ouverture -- pas au
  // montage du widget (qui a lieu des l'arrivee sur la page, meme si
  // l'utilisateur n'ouvre jamais la bulle) : evite un appel reseau inutile
  // sur chaque visite de PacteFondateursV2Page.
  useEffect(() => {
    if (!isOpen || hasLoadedHistory || !accessToken) return

    setIsLoadingHistory(true)
    setError(null)
    getHistorique(accessToken, projectId)
      .then(({ echanges }) => {
        const historiqueAffiche: CopilotDisplayMessage[] = echanges.flatMap((echange) => [
          { role: "user" as const, content: echange.question },
          { role: "assistant" as const, content: echange.reponse, sources: echange.sources },
        ])
        setMessages(historiqueAffiche)
        setHasLoadedHistory(true)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger l'historique."))
      .finally(() => setIsLoadingHistory(false))
  }, [isOpen, hasLoadedHistory, accessToken, projectId])

  // Efface le badge "non lu" a l'ouverture -- separe de l'effet ci-dessus
  // (qui ne s'execute qu'une fois, tant que hasLoadedHistory est false).
  useEffect(() => {
    if (isOpen) setHasUnseenAutoExplanation(false)
  }, [isOpen])

  // Service 1.1.15 (27/09/2026) -- pousse une explication automatique des
  // qu'une nouvelle clause devient le contexte courant (nouvelle section
  // affichee dans le questionnaire). Best-effort et silencieux (comme
  // refreshPreview() cote page) : un echec ici n'empeche jamais de continuer
  // a remplir le questionnaire, la bulle reste utilisable a la main.
  useEffect(() => {
    if (!accessToken || !clauseContexte) return
    if (autoExplainedClauses.has(clauseContexte.code_clause)) return

    const { code_clause, documentType, codeSection } = clauseContexte
    pousserExplicationAutomatique(accessToken, projectId, documentType, codeSection)
      .then((resultat) => {
        setAutoExplainedClauses((prev) => new Set(prev).add(code_clause))
        if (!resultat) return // section sans clause unique (variante pas encore choisie, texte fixe...)

        // N'ajoute localement que si l'historique est deja charge (bulle deja
        // ouverte au moins une fois) -- sinon la prochaine ouverture le
        // recuperera via getHistorique(), l'ajouter ici aussi creerait un
        // doublon visuel.
        if (hasLoadedHistory) {
          setMessages((prev) => [
            ...prev,
            { role: "user", content: resultat.question },
            { role: "assistant", content: resultat.reponse, sources: [] },
          ])
        }
        if (!isOpen) setHasUnseenAutoExplanation(true)
      })
      .catch(() => {
        // Silencieux : l'utilisateur garde la suggestion "Explique-moi cette
        // clause" comme filet de secours si l'auto-push echoue.
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, projectId, clauseContexte?.code_clause])

  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isSending])

  async function envoyerQuestion(question: string) {
    const texte = question.trim()
    if (!texte || !accessToken || isSending) return

    setMessages((prev) => [...prev, { role: "user", content: texte }])
    setInputValue("")
    setIsSending(true)
    setError(null)
    if (clauseContexte) setSuggestionsDismissedForClause(clauseContexte.code_clause)

    try {
      const reponse = await poserQuestion(accessToken, projectId, texte, clauseContexte?.code_clause ?? null)
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reponse.reponse, sources: reponse.sources as PacteFondateurCopilotSource[] },
      ])
    } catch (err) {
      // Le message utilisateur reste affiche (deja ajoute ci-dessus) mais
      // sans reponse -- coherent avec obtenir_historique() cote backend qui,
      // lui, filtre ce cas plutot que de le persister a moitie.
      setError(err instanceof ApiError ? err.message : "Le copilot n'a pas pu repondre, reessaie dans un instant.")
    } finally {
      setIsSending(false)
    }
  }

  function handleSubmit(evenement: FormEvent) {
    evenement.preventDefault()
    envoyerQuestion(inputValue)
  }

  const suggestions = buildSuggestions(
    clauseContexte,
    clauseContexte ? autoExplainedClauses.has(clauseContexte.code_clause) : false,
  )
  const showSuggestions =
    !isLoadingHistory && suggestions.length > 0 && clauseContexte?.code_clause !== suggestionsDismissedForClause

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {isOpen && (
        <div className="mb-3 flex h-[520px] w-[360px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between bg-gradient-to-r from-indigo-600 to-indigo-500 px-4 py-3 text-white">
            <div>
              <p className="text-sm font-semibold">Copilot pacte de fondateurs</p>
              <p className="text-xs text-indigo-100">
                {clauseContexte ? `Sur : ${clauseContexte.titre_clause}` : "Questions sur le pacte en general"}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-full p-1 text-indigo-100 hover:bg-white/10 hover:text-white"
              aria-label="Fermer le copilot"
            >
              <CloseIcon />
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
            {isLoadingHistory && <p className="text-center text-xs text-slate-400">Chargement de la conversation...</p>}

            {messages.length === 0 && !isLoadingHistory && (
              <p className="text-xs text-slate-500">Bonjour ! Sur quoi puis-je t'aider ?</p>
            )}

            {messages.map((message, index) => (
              <PacteFondateurCopilotMessage key={index} role={message.role} content={message.content} sources={message.sources} />
            ))}

            {isSending && <p className="text-xs text-slate-400">Le copilot repond...</p>}
            {error && <p className="text-xs text-red-600">{error}</p>}

            <div ref={scrollAnchorRef} />
          </div>

          {/* Barre de suggestions ancree au-dessus du champ de saisie (pas
              dans la liste de messages qui defile) -- se re-affiche a chaque
              changement de clause, voir suggestionsDismissedForClause. */}
          {showSuggestions && (
            <div className="flex flex-wrap gap-2 border-t border-slate-200 px-3 pt-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => envoyerQuestion(suggestion)}
                  className="rounded-full border border-indigo-200 px-3 py-1.5 text-xs text-indigo-700 hover:bg-indigo-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={handleSubmit}
            className={`flex items-center gap-2 p-2 ${showSuggestions ? "" : "border-t border-slate-200"}`}
          >
            <input
              type="text"
              value={inputValue}
              onChange={(evenement) => setInputValue(evenement.target.value)}
              placeholder="Pose ta question..."
              disabled={isSending}
              className="flex-1 rounded-full border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={isSending || !inputValue.trim()}
              className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
              aria-label="Envoyer"
            >
              <SendIcon />
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="relative flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg hover:bg-indigo-500"
        aria-label={isOpen ? "Fermer le copilot" : "Ouvrir le copilot"}
      >
        {isOpen ? <CloseIcon /> : <ChatIcon />}
        {/* Point "non lu" -- signale une explication poussee automatiquement
         * pendant que la bulle etait fermee (service 1.1.15), sans forcer
         * l'ouverture : reste discret plutot que d'interrompre la saisie. */}
        {hasUnseenAutoExplanation && !isOpen && (
          <span className="absolute right-0.5 top-0.5 h-3 w-3 rounded-full border-2 border-white bg-amber-400" />
        )}
      </button>
    </div>
  )
}

/** Suggestions contextuelles : "expliquer cette clause" + jusqu'a
 * MAX_SUGGESTIONS_VARIABLES suggestions d'impact de variable, seulement si
 * une clause est affichee. Limitee volontairement (pas une par variable,
 * une clause peut en avoir 6-8) pour ne pas saturer visuellement la bulle --
 * les autres restent accessibles en tapant une question libre.
 *
 * BUG CORRIGE (25/09/2026) : la version precedente n'envoyait que le
 * libelle humain de la variable dans le texte du message ("numero
 * d'article des statuts"). Le LLM devait alors deviner le `nom_variable`
 * technique attendu par le tool expliquer_impact_variable -- meme classe de
 * bug que le code_clause devine (voir pacte_fondateur_copilot_agent.py) :
 * sans le nom technique ecrit noir sur blanc quelque part dans la
 * conversation, le modele ne peut que l'inventer. Le nom technique est
 * maintenant inclus verbatim dans le texte envoye (visible utilisateur,
 * mais reste lisible car accole au libelle).
 *
 * `dejaExpliqueeAuto` (27/09/2026, service 1.1.15) : masque la 1ere
 * suggestion quand l'explication automatique a deja ete poussee pour cette
 * clause -- redemander "explique-moi cette clause" juste apres se l'etre
 * fait dire spontanement n'apporte rien. Les suggestions d'impact de
 * variable restent : elles couvrent un besoin different, jamais couvert par
 * l'explication automatique (generique, sans valeur saisie particuliere). */
function buildSuggestions(clauseContexte: CopilotClauseContexte | null, dejaExpliqueeAuto: boolean): string[] {
  if (!clauseContexte) return []

  const suggestions = dejaExpliqueeAuto ? [] : [`Explique-moi la clause "${clauseContexte.titre_clause}"`]
  const variables = clauseContexte.variables ?? []
  for (const variable of variables.slice(0, MAX_SUGGESTIONS_VARIABLES)) {
    suggestions.push(
      `Quel est l'impact de la variable "${variable.nom}" (${variable.libelle}) sur cette clause ?`,
    )
  }
  return suggestions
}

function ChatIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-6 w-6">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.625 12a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H8.25m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0H12m4.125 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 0 1-2.555-.337A5.972 5.972 0 0 1 5.41 20.97a5.969 5.969 0 0 1-.474-.065 4.48 4.48 0 0 0 .978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25Z"
      />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-5 w-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-4 w-4">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.126A59.768 59.768 0 0 1 21.485 12 59.77 59.77 0 0 1 3.27 20.876L5.999 12Zm0 0h7.5" />
    </svg>
  )
}
