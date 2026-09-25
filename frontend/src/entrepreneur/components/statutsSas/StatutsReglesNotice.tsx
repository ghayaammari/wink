import type { GuardrailBlockedDetail, RegleProbleme } from "../../api/documentGenerationApi"

interface Props {
  detail: GuardrailBlockedDetail
  /** Problèmes sans champ affiché dans le formulaire : montrés ici en entier
   * pour ne jamais perdre une erreur (cas défensif). */
  problemesHorsChamp: RegleProbleme[]
  isSubmitting: boolean
  /** Renvoie la même saisie en confirmant les avertissements. */
  onConfirmer: () => void
  /** Fait défiler jusqu'au premier champ en faute. */
  onAllerAuPremier: () => void
}

/**
 * Résumé d'une ligne sous le bouton de validation (garde-fou des statuts,
 * 24/09/2026). Le détail de chaque problème est affiché SOUS SON CHAMP
 * (StatutsChampAlerte) -- plus de liste complète ici (retour utilisateur :
 * trop chargé, loin des champs concernés).
 * - Blocage : « N champs à corriger » (clic -> premier champ).
 * - Avertissements seuls : « N points à vérifier » + « Continuer quand même ».
 */
export default function StatutsReglesNotice({
  detail,
  problemesHorsChamp,
  isSubmitting,
  onConfirmer,
  onAllerAuPremier,
}: Props) {
  const problemes = detail.problemes ?? []
  if (problemes.length === 0) return null
  const avertissementsSeulement = problemes.every((p) => p.gravite === "avertissement")
  const nbChamps = new Set(problemes.map((p) => `${p.variable}|${p.associe_id ?? ""}`)).size
  const libelle = avertissementsSeulement
    ? `${nbChamps} point${nbChamps > 1 ? "s" : ""} à vérifier`
    : `${nbChamps} champ${nbChamps > 1 ? "s" : ""} à corriger`
  const couleur = avertissementsSeulement
    ? "border-amber-200 bg-amber-50 text-amber-900"
    : "border-red-200 bg-red-50 text-red-900"

  return (
    <div className={`flex flex-col gap-2 rounded-lg border px-3 py-2 text-sm ${couleur}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <button type="button" onClick={onAllerAuPremier} className="font-medium hover:underline">
          {avertissementsSeulement ? "⚠️" : "⛔"} {libelle} ↑
        </button>
        {avertissementsSeulement && (
          <button
            type="button"
            onClick={onConfirmer}
            disabled={isSubmitting}
            className="rounded-md border border-amber-400 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-50"
          >
            Continuer quand même
          </button>
        )}
      </div>
      {problemesHorsChamp.map((p, i) => (
        <p key={i} className="text-xs">
          « {p.libelle} » : {p.message}
        </p>
      ))}
    </div>
  )
}
