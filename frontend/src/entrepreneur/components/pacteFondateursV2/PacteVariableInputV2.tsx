import type { ClauseVariable } from "../../api/documentGenerationApi"

interface PacteVariableInputV2Props {
  variable: ClauseVariable
  value: string
  onChange: (value: string) => void
  /** Valeur déjà résolue côté backend pour une variable `auto_*`
   * (ClauseCandidateRead.valeurs_auto_resolues[variable.nom]) — ignorée pour
   * tout autre type. `undefined` = donnée source manquante côté projet. */
  resolvedValue?: string
}

function isAutoType(type: string): boolean {
  return type.startsWith("auto_")
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

/**
 * Fork v2 de `PacteVariableInput` (pacteFondateurs/), pour un seul
 * changement demandé : `choix` se rend en boutons radio plutôt qu'en
 * `<select>` natif — l'original v1 n'est pas touché (règle actée avec
 * l'utilisateur, 21/09/2026 : tout composant partagé qu'on veut modifier pour
 * v2 est forké, jamais édité en place).
 *
 * Tous les autres types de variable (texte/nombre/montant/duree/date/
 * nombre_ordinal) restent identiques à la v1 — dupliqués ici plutôt que
 * partagés via un composant commun : le seul point de variation entre v1/v2
 * est `choix`, extraire un sous-composant commun pour 6 branches identiques
 * aurait ajouté une indirection sans réduire la duplication réelle (~15
 * lignes). Si d'autres types divergent aussi entre v1/v2 à l'avenir, cet
 * arbitrage sera à revoir.
 */
export default function PacteVariableInputV2({
  variable,
  value,
  onChange,
  resolvedValue,
}: PacteVariableInputV2Props) {
  if (variable.type === "reference_croisee") return null

  const fieldId = `pacte-variable-${variable.nom}`

  // Variables auto_* (24/09/2026) : jamais un champ éditable — déjà résolues
  // côté backend (ProjectLegalProfile / project_associates, voir
  // _resoudre_variables_auto). Affichées en lecture seule, "(non renseigné)"
  // si la donnée source manque côté projet plutôt qu'un blanc silencieux —
  // non bloquant pour "Valider cette section" (voir missingRequired dans
  // PacteSectionFormV2, qui exclut ces types).
  if (isAutoType(variable.type)) {
    return (
      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor={fieldId}>
          {variable.libelle}
        </label>
        <div
          id={fieldId}
          className={`${inputClass} cursor-not-allowed bg-gray-50 text-gray-600`}
        >
          {resolvedValue || "(non renseigné)"}
        </div>
        {/* 24/09/2026 (confusion utilisateur constatée sur la clause 10.3
         * Mandataire) : le champ grisé seul ne disait pas QUE la valeur est
         * automatique ni D'OÙ elle vient -- juste "non modifiable" ne
         * suffisait pas à comprendre pourquoi il contient déjà un texte.
         * Une seule phrase générique ici plutôt qu'un texte par variable :
         * toutes les variables auto_* partagent la même raison d'être
         * (résolues depuis le profil du projet, jamais depuis une saisie),
         * seule la donnée source change. */}
        <p className="text-xs text-gray-400">
          Rempli automatiquement à partir des informations de ton projet (forme juridique, associés...) — rien à
          saisir ici.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label className={labelClass} htmlFor={fieldId}>
        {variable.libelle}
      </label>

      {variable.type === "choix" ? (
        <div role="radiogroup" aria-labelledby={fieldId} className="flex flex-col gap-1.5">
          {(variable.options ?? []).map((option) => {
            const optionId = `${fieldId}-${option}`
            return (
              <label
                key={option}
                htmlFor={optionId}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
                  value === option
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-gray-300 text-gray-700 hover:border-gray-400"
                }`}
              >
                <input
                  id={optionId}
                  type="radio"
                  name={fieldId}
                  value={option}
                  checked={value === option}
                  onChange={() => onChange(option)}
                  className="h-4 w-4"
                />
                {option}
              </label>
            )
          })}
        </div>
      ) : variable.type === "texte" ? (
        <textarea
          id={fieldId}
          className={`${inputClass} min-h-[88px]`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          id={fieldId}
          className={inputClass}
          type={variable.type === "date" ? "date" : variable.type === "nombre" ? "number" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            variable.type === "montant"
              ? "ex : 10 000 €"
              : variable.type === "duree"
                ? "ex : 3 ans"
                : variable.type === "nombre_ordinal"
                  ? "ex : premier"
                  : undefined
          }
        />
      )}
    </div>
  )
}
