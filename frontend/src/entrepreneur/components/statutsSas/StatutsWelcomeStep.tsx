import { useState, type FormEvent } from "react"

interface StatutsWelcomeStepProps {
  onStart: () => void
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"

const EXPLICATION = `Les statuts sont le contrat fondateur de la société : déposés au greffe et
opposables aux tiers (contrairement au pacte de fondateurs, qui reste
confidentiel entre associés), ils fixent ce que la loi exige pour
l'immatriculation — forme juridique, objet social, dénomination, siège
social, durée, capital et apports de chaque associé, organes de direction.

Ils sont obligatoires : sans statuts signés, la société ne peut pas être
immatriculée. Ce questionnaire les rédige article par article, en réutilisant
les informations déjà renseignées dans "Équipe & capital" et "Informations
légales" quand elles sont disponibles.`

// Même détection d'intention très simple que PacteWelcomeStep (voir sa
// docstring pour le pourquoi) — pas dupliquée dans un module commun : les 2
// fichiers divergent déjà sur le texte d'accueil/l'explication, qui est le
// seul contenu réel de ce composant ; extraire seulement cette fonction de 3
// lignes n'aurait réduit aucune duplication utile.
function looksLikeStartIntent(text: string): boolean {
  const normalized = text.trim().toLowerCase()
  return /(commenc|génér|generer|c'est parti|go|oui)/.test(normalized)
}

/**
 * Fork de `PacteWelcomeStep` (pacteFondateurs/) pour le service 1.1.4
 * (statuts) — FORKÉ plutôt que réutilisé tel quel : contrairement à
 * `PacteGuardrailNotice` (générique, aucun texte propre au pacte), ce
 * composant est entièrement fait de texte explicatif spécifique au pacte de
 * fondateurs (voir EXPLICATION ci-dessus vs. la version pacte) — le
 * réutiliser pour les statuts aurait affiché une explication du mauvais
 * document. Même règle que PacteVariableInputV2/PacteSectionFormV2 (21/09/2026) :
 * un composant qu'on doit modifier pour un autre document_type est forké,
 * jamais édité en place ni réutilisé avec un contenu qui ne lui correspond
 * plus.
 */
export default function StatutsWelcomeStep({ onStart }: StatutsWelcomeStepProps) {
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
        Bienvenue ! Veux-tu commencer la rédaction des statuts de ta société, ou que je t'explique
        d'abord ce que c'est et ce qu'ils contiennent ?
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
          Commencer la rédaction
        </button>
        <button
          type="button"
          onClick={() => setShowExplication(true)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          M'expliquer ce que sont les statuts
        </button>
      </div>

      <form onSubmit={handleFreeTextSubmit} className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-gray-700" htmlFor="statuts-welcome-free-text">
          Ou réponds directement en texte libre
        </label>
        <div className="flex gap-2">
          <input
            id="statuts-welcome-free-text"
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
