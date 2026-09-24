import type { ClauseVariable, RegleProbleme } from "../../api/documentGenerationApi"
import StatutsChampAlerte, { classeBordure } from "./StatutsChampAlerte"

type SelectionCandidat = { id: string; libelle: string }

interface StatutsVariableInputProps {
  variable: ClauseVariable
  /** Chaîne pour tout type "normal" (y compris `auto_identite_associe` avec
   * un vrai choix, où c'est l'id de l'associé sélectionné) ; objet
   * `{ [associateId]: valeur }` seulement pour `texte_par_associe`/
   * `nombre_par_associe` (voir StatutsSectionForm — `valeurs` y est élargi
   * en conséquence, même type que `SectionAnswerSubmit.valeurs`). */
  value: string | Record<string, string>
  onChange: (value: string | Record<string, string>) => void
  /** Valeur déjà résolue côté backend pour une variable `auto_*` classique,
   * ou pour `auto_identite_associe` quand elle n'a PAS besoin d'un choix
   * (0 ou 1 candidat — voir `candidats` ci-dessous). */
  resolvedValue?: string
  /** Rempli uniquement si `ClauseCandidateRead.selections_requises` liste
   * cette variable — c'est-à-dire seulement pour `auto_identite_associe`
   * avec PLUSIEURS candidats (vrai choix) et pour `texte_par_associe`/
   * `nombre_par_associe` (toujours, dès qu'au moins un associé est
   * concerné). `undefined` sinon. */
  candidats?: SelectionCandidat[]
  /** Problèmes du garde-fou (niveaux A/B) pour cette variable : affichés
   * sous le champ -- sous la case de l'associé concerné pour une saisie par
   * associé (`associe_id`). */
  problemes?: RegleProbleme[]
}

function isAutoType(type: string): boolean {
  return type.startsWith("auto_")
}

const inputBase = "w-full rounded-lg border px-3 py-2 text-sm"
const inputClass = `${inputBase} border-gray-300`

/** Classe du champ : bordure rouge/orange s'il a un problème. Deux classes
 * de couleur de bordure ne sont jamais combinées (l'ordre du CSS généré, pas
 * celui des classes, déciderait laquelle gagne). */
function classeChamp(problemes: RegleProbleme[] | undefined): string {
  const bordure = classeBordure(problemes)
  return bordure ? `${inputBase} ${bordure}` : inputClass
}
const labelClass = "text-xs font-medium text-gray-700"

/**
 * Fork de `PacteVariableInputV2` (pacteFondateursV2/) pour le service 1.1.4
 * (statuts) — le clausier des statuts introduit 2 types de variable absents
 * du pacte, qui ont besoin d'un rendu différent des simples champs auto_* /
 * texte / nombre déjà couverts par l'original :
 *
 * - `auto_identite_associe` : résolue automatiquement (comme les autres
 *   auto_*) s'il n'y a que 0 ou 1 associé concerné, mais devient un VRAI
 *   choix (menu déroulant) dès qu'il y en a plusieurs — ex. Article 8
 *   `fondateur_avantage` (pacte) ou une clause à plusieurs apporteurs
 *   possibles côté statuts. Distingué ici via `candidats` (rempli seulement
 *   dans ce cas par `ClauseCandidateRead.selections_requises`, voir
 *   StatutsSectionForm).
 * - `texte_par_associe`/`nombre_par_associe` : jamais un choix, mais une
 *   saisie répétée UNE FOIS PAR associé listé dans `candidats` (ex. Article 6
 *   `designation_bien_apporte` par apporteur en nature) — rendue comme N
 *   champs, un par associé, plutôt qu'un champ unique.
 *
 * Le pacte n'a pas ce cas de figure aujourd'hui (son seul `auto_identite_associe`
 * multi-candidats, Article 8, n'a jamais eu besoin d'être forké côté pacte
 * puisque son formulaire actuel ne le traite pas encore) — pas de 3e fork
 * pour ce fichier, celui-ci suffit pour l'instant aux 2 documents qui en
 * auraient besoin s'ils exposaient `selections_requises` au frontend.
 */
export default function StatutsVariableInput({
  variable,
  value,
  onChange,
  resolvedValue,
  candidats,
  problemes = [],
}: StatutsVariableInputProps) {
  if (variable.type === "reference_croisee") return null

  const fieldId = `statuts-variable-${variable.nom}`
  // Problèmes sans associé précis (cas général) ; ceux d'un associé sont
  // filtrés plus bas, case par case.
  const problemesChamp = problemes.filter((p) => !p.associe_id)

  if (variable.type === "auto_identite_associe" && candidats && candidats.length > 0) {
    const selected = typeof value === "string" ? value : ""
    return (
      <div className="flex flex-col gap-1.5" data-champ={variable.nom}>
        <label className={labelClass} htmlFor={fieldId}>
          {variable.libelle}
        </label>
        <select
          id={fieldId}
          className={classeChamp(problemesChamp)}
          value={selected}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="" disabled>
            Choisir un associé…
          </option>
          {candidats.map((c) => (
            <option key={c.id} value={c.id}>
              {c.libelle}
            </option>
          ))}
        </select>
        <StatutsChampAlerte problemes={problemesChamp} />
      </div>
    )
  }

  if (variable.type === "texte_par_associe" || variable.type === "nombre_par_associe") {
    const valeursParAssocie = typeof value === "object" && value !== null ? value : {}
    if (!candidats || candidats.length === 0) {
      // Cas limite : le backend n'a résolu aucun candidat pour cette variable
      // (ex. aucun associé n'a le type d'apport concerné) — signalé plutôt
      // qu'un champ vide sans explication, cohérent avec le reste de l'app.
      return (
        <div className="flex flex-col gap-1.5">
          <label className={labelClass}>{variable.libelle}</label>
          <p className="text-xs text-gray-400">(aucun associé concerné par ce champ)</p>
        </div>
      )
    }
    return (
      <div className="flex flex-col gap-2" data-champ={variable.nom}>
        <span className={labelClass}>{variable.libelle}</span>
        <StatutsChampAlerte problemes={problemesChamp} />
        {candidats.map((c) => {
          const associeFieldId = `${fieldId}-${c.id}`
          const problemesAssocie = problemes.filter((p) => p.associe_id === c.id)
          return (
            <div key={c.id} className="flex flex-col gap-1" data-champ-associe={c.id}>
              <label className="text-xs text-gray-500" htmlFor={associeFieldId}>
                {c.libelle}
              </label>
              <input
                id={associeFieldId}
                className={classeChamp(problemesAssocie)}
                type={variable.type === "nombre_par_associe" ? "number" : "text"}
                value={valeursParAssocie[c.id] ?? ""}
                onChange={(e) => onChange({ ...valeursParAssocie, [c.id]: e.target.value })}
              />
              <StatutsChampAlerte
                problemes={problemesAssocie}
                onUtiliserProposition={(texte) => onChange({ ...valeursParAssocie, [c.id]: texte })}
              />
            </div>
          )
        })}
      </div>
    )
  }

  // Variables auto_* restantes (résolution automatique complète, y compris
  // `auto_identite_associe` sans choix requis, voir plus haut) — même rendu
  // et même texte explicatif que PacteVariableInputV2, voir sa docstring
  // pour le pourquoi (confusion utilisateur constatée sur un champ grisé
  // sans explication).
  if (isAutoType(variable.type)) {
    return (
      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor={fieldId}>
          {variable.libelle}
        </label>
        <div id={fieldId} className={`${inputClass} cursor-not-allowed bg-gray-50 text-gray-600`}>
          {resolvedValue || "(non renseigné)"}
        </div>
        <p className="text-xs text-gray-400">
          Rempli automatiquement à partir des informations de ton projet (forme juridique, associés...) — rien à
          saisir ici.
        </p>
      </div>
    )
  }

  const stringValue = typeof value === "string" ? value : ""

  return (
    <div className="flex flex-col gap-1.5" data-champ={variable.nom}>
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
                  stringValue === option
                    ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                    : "border-gray-300 text-gray-700 hover:border-gray-400"
                }`}
              >
                <input
                  id={optionId}
                  type="radio"
                  name={fieldId}
                  value={option}
                  checked={stringValue === option}
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
          className={`${classeChamp(problemesChamp)} min-h-[88px]`}
          value={stringValue}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          id={fieldId}
          className={classeChamp(problemesChamp)}
          type={variable.type === "date" ? "date" : variable.type === "nombre" ? "number" : "text"}
          value={stringValue}
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
      <StatutsChampAlerte problemes={problemesChamp} onUtiliserProposition={(texte) => onChange(texte)} />
    </div>
  )
}
