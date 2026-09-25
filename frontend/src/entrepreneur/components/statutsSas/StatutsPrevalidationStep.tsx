import { Link } from "react-router-dom"
import type { PrevalidationPage, PrevalidationProbleme } from "../../api/documentGenerationApi"

/**
 * Écran « Avant de commencer » des statuts (pré-validation, 24/09/2026) :
 * affiché au clic « Commencer » s'il manque des données du projet que les
 * statuts reprennent automatiquement. Regroupé par page, avec un lien direct
 * vers chacune ; « Vérifier à nouveau » relance le contrôle au retour.
 *
 * Bloquant par décision utilisateur : sans ces données, le document
 * sortirait avec des « (… non renseigné) ».
 */

/** Pages du projet où corriger une donnée (réutilisé par la vérification finale). */
export const PAGES_PROJET: { page: PrevalidationPage; titre: string; lien: string }[] = [
  { page: "informations_legales", titre: "Informations légales", lien: "/entrepreneur/mon-projet/informations-legales" },
  { page: "equipe_capital", titre: "Équipe & capital", lien: "/entrepreneur/mon-projet/equipe-capital" },
  { page: "dirigeants", titre: "Dirigeants", lien: "/entrepreneur/mon-projet/dirigeants" },
]

interface Props {
  problemes: PrevalidationProbleme[]
  isChecking: boolean
  onRecheck: () => void
  onBack: () => void
}

export default function StatutsPrevalidationStep({ problemes, isChecking, onRecheck, onBack }: Props) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border border-amber-200 bg-white p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Avant de commencer</h2>
        <p className="mt-1 text-sm text-gray-600">
          Vos statuts reprennent automatiquement certaines informations de votre projet. Complétez-les pour pouvoir
          commencer : vous n'aurez pas à les ressaisir pendant la rédaction.
        </p>
      </div>

      {PAGES_PROJET.map(({ page, titre, lien }) => {
        const duGroupe = problemes.filter((p) => p.page === page)
        if (duGroupe.length === 0) return null
        return (
          <section key={page} className="flex flex-col gap-2 rounded-lg border border-gray-100 bg-gray-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-gray-900">{titre}</h3>
              <Link
                to={lien}
                className="rounded-lg border border-indigo-300 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
              >
                Compléter →
              </Link>
            </div>
            <ul className="flex list-disc flex-col gap-1 pl-5 text-sm text-gray-700">
              {duGroupe.map((p) => (
                <li key={p.code}>{p.message}</li>
              ))}
            </ul>
          </section>
        )
      })}

      <div className="flex justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          Retour
        </button>
        <button
          type="button"
          onClick={onRecheck}
          disabled={isChecking}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {isChecking ? "Vérification..." : "Vérifier à nouveau"}
        </button>
      </div>
    </div>
  )
}
