import { useState, type FormEvent } from "react"

interface PacteWelcomeStepProps {
  onStart: () => void
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"

const EXPLICATION = `Un pacte de fondateurs (ou pacte d'associés) est un contrat signé entre les
associés d'une société, en complément des statuts. Il organise les relations
entre associés sur des sujets que les statuts ne couvrent pas en détail :
gouvernance, mouvements de titres (préemption, sortie conjointe, sortie
forcée), inaliénabilité temporaire des titres, non-concurrence, etc.

Contrairement aux statuts (publics, opposables aux tiers), le pacte reste
confidentiel entre ses signataires. Il permet de prévoir à l'avance comment
gérer les situations délicates entre associés (désaccord, départ, arrivée
d'un investisseur) avant qu'elles ne se produisent.`

// Détection d'intention très simple sur le texte libre — le scénario demande
// un double canal de réponse (boutons ou texte libre), pas une compréhension
// de langage naturel poussée pour cette seule bifurcation à 2 issues. Un vrai
// besoin d'interprétation LLM apparaîtrait si cet écran devait un jour
// répondre à des questions ouvertes plutôt qu'à ce choix binaire — pas le cas
// ici (voir agents/ vs backend/, on n'ajoute pas d'appel LLM pour ça).
function looksLikeStartIntent(text: string): boolean {
  const normalized = text.trim().toLowerCase()
  return /(commenc|génér|generer|c'est parti|go|oui)/.test(normalized)
}

/**
 * Étape 0 du scénario — accueil et orientation. Deux chemins (boutons) + champ
 * de texte libre. "M'expliquer" reste sur cet écran (relance la même
 * proposition après l'explication, comme demandé) ; seul "Commencer" fait
 * remonter `onStart` vers PacteFondateursPage, qui charge alors la première
 * section réelle depuis l'API.
 */
export default function PacteWelcomeStep({ onStart }: PacteWelcomeStepProps) {
  const [showExplication, setShowExplication] = useState(false)
  const [freeText, setFreeText] = useState("")

  function handleFreeTextSubmit(e: FormEvent) {
    e.preventDefault()
    if (looksLikeStartIntent(freeText)) {
      onStart()
      return
    }
    setShowExplication(true)
    setFreeText("")
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg bg-indigo-50 p-4 text-sm text-gray-800">
        Bienvenue ! Veux-tu commencer la génération de ton pacte de fondateurs, ou que je t'explique
        d'abord ce que c'est et ce qu'il contient ?
      </div>

      {showExplication && (
        <div className="whitespace-pre-line rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700">
          {EXPLICATION}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onStart}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Commencer la génération
        </button>
        <button
          type="button"
          onClick={() => setShowExplication(true)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          M'expliquer ce qu'est un pacte d'associés
        </button>
      </div>

      <form onSubmit={handleFreeTextSubmit} className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-gray-700" htmlFor="pacte-welcome-free-text">
          Ou réponds directement en texte libre
        </label>
        <div className="flex gap-2">
          <input
            id="pacte-welcome-free-text"
            className={inputClass}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="ex : oui, c'est parti"
          />
          <button
            type="submit"
            className="shrink-0 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            Envoyer
          </button>
        </div>
      </form>
    </div>
  )
}
