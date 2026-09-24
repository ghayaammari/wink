import { useState } from "react"
import type { FacultatifRead } from "../../api/documentGenerationApi"
import { Icon, ICON_CHECK, ICON_CHEVRON_LEFT, ICON_INFO, ICON_MINUS, ICON_PLUS } from "../pacteFondateursV2/pacteIcons"

interface StatutsFacultatifsStepProps {
  titre: string | null
  explication: string | null
  facultatifs: FacultatifRead[]
  isSubmitting: boolean
  onSubmit: (codesChoisis: string[]) => void
  onBack: () => void
}

/**
 * Écran de choix des articles facultatifs des statuts (service 1.1.4,
 * audit #19, 24/09/2026) — affiché quand le backend met le parcours en pause
 * juste avant l'Art. 8 (`section.choix_facultatifs_requis`).
 *
 * Pourquoi ici et pas à la fin : le moteur écarte définitivement une section
 * dont la condition est fausse au moment où il la croise ; plusieurs articles
 * (14, 17, 27…) dépendent des facultatifs choisis, qui doivent donc être
 * connus avant. L'Art. 8 est le 1er facultatif et aucun des Art. 1-7 n'en
 * dépend.
 *
 * Chaque article a une explication dépliable. Les explications sont des
 * textes courts provisoires (voir FACULTATIFS_STATUTS côté backend) — à
 * remplacer par les explications générées et relues, sans toucher à cet écran.
 */
export default function StatutsFacultatifsStep({
  titre,
  explication,
  facultatifs,
  isSubmitting,
  onSubmit,
  onBack,
}: StatutsFacultatifsStepProps) {
  const [choisis, setChoisis] = useState<Set<string>>(
    () => new Set(facultatifs.filter((f) => f.choisi).map((f) => f.code)),
  )
  const [ouverts, setOuverts] = useState<Set<string>>(() => new Set())

  function basculer(set: Set<string>, code: string): Set<string> {
    const suivant = new Set(set)
    if (suivant.has(code)) suivant.delete(code)
    else suivant.add(code)
    return suivant
  }

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        disabled={isSubmitting}
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Icon path={ICON_CHEVRON_LEFT} className="h-3.5 w-3.5" />
        Section précédente
      </button>

      <div className="flex flex-col gap-1.5">
        <h2 className="text-base font-semibold text-gray-900">{titre ?? "Les protections de vos statuts"}</h2>
        {explication && (
          <div className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
            <Icon path={ICON_INFO} className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
            <p>{explication}</p>
          </div>
        )}
      </div>

      <ul className="flex flex-col gap-2">
        {facultatifs.map((f) => {
          const estChoisi = choisis.has(f.code)
          const estOuvert = ouverts.has(f.code)
          return (
            <li
              key={f.code}
              className={`rounded-lg border bg-white p-3 ${estChoisi ? "border-indigo-400" : "border-gray-200"}`}
            >
              <div className="flex items-start gap-3">
                <input
                  id={`facultatif-${f.code}`}
                  type="checkbox"
                  checked={estChoisi}
                  onChange={() => setChoisis((prev) => basculer(prev, f.code))}
                  className="mt-1 h-4 w-4 rounded border-gray-300 text-indigo-600"
                />
                <div className="flex flex-1 flex-col gap-1">
                  <label htmlFor={`facultatif-${f.code}`} className="text-sm font-medium text-gray-900">
                    {f.titre}
                    <span className="ml-2 text-xs font-normal text-gray-500">
                      Art. {f.articles.join(" et ")}
                    </span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setOuverts((prev) => basculer(prev, f.code))}
                    className="inline-flex w-fit items-center gap-1 text-xs text-indigo-600 hover:text-indigo-500"
                  >
                    <Icon path={estOuvert ? ICON_MINUS : ICON_PLUS} className="h-3 w-3" />
                    {estOuvert ? "Masquer l'explication" : "À quoi ça sert ?"}
                  </button>
                  {estOuvert && <p className="text-xs text-gray-600">{f.explication}</p>}

                </div>
              </div>
            </li>
          )
        })}
      </ul>

      <p className="text-xs text-gray-500">
        Vous pourrez encore retirer un article coché au moment où il s'affiche. Ne rien cocher est possible :
        seuls les articles obligatoires seront rédigés.
      </p>

      <button
        type="button"
        disabled={isSubmitting}
        onClick={() => onSubmit(facultatifs.filter((f) => choisis.has(f.code)).map((f) => f.code))}
        className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Icon path={ICON_CHECK} className="h-4 w-4" />
        Valider mon choix ({choisis.size})
      </button>
    </div>
  )
}
