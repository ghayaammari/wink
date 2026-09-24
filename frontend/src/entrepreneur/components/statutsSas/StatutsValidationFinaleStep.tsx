import { useState } from "react"
import { Link } from "react-router-dom"
import type { EtapeValidation, ProblemeValidation, ValidationFinaleRead } from "../../api/documentGenerationApi"
import { PAGES_PROJET } from "./StatutsPrevalidationStep"

interface Props {
  /** null = vérification en cours de chargement. */
  validation: ValidationFinaleRead | null
  isChecking: boolean
  isGenerating: boolean
  onRecheck: () => void
  /** Rouvre une section du parcours (« Corriger → »). */
  onCorriger: (codeSection: string) => void
  /** « Appliquer » : enregistre la correction certaine puis revérifie. */
  onAppliquer: (probleme: ProblemeValidation) => void
  onGenerer: () => void
}

const ICONE_ETAPE: Record<EtapeValidation["statut"], string> = { ok: "✓", problemes: "!", erreur: "✕" }
const COULEUR_ETAPE: Record<EtapeValidation["statut"], string> = {
  ok: "bg-green-100 text-green-700",
  problemes: "bg-amber-100 text-amber-700",
  erreur: "bg-gray-200 text-gray-600",
}

function ProblemeLigne({
  p,
  onCorriger,
  onAppliquer,
  isBusy,
}: {
  p: ProblemeValidation
  onCorriger: (code: string) => void
  onAppliquer: (p: ProblemeValidation) => void
  isBusy: boolean
}) {
  const [ouvert, setOuvert] = useState(false)
  const bloquant = p.gravite === "bloquant"
  const page = p.cible_type === "page" ? PAGES_PROJET.find((x) => x.page === p.cible) : undefined
  // Une reformulation déjà affichée comme correction n'est pas répétée.
  const reformulation = p.reformulation_proposee && p.reformulation_proposee !== p.correction_proposee

  return (
    <li className={`flex flex-col gap-2 rounded-lg border bg-white px-3 py-2.5 ${bloquant ? "border-red-200" : "border-amber-200"}`}>
      <div className="flex flex-col gap-0.5">
        <p className={`text-sm font-medium ${bloquant ? "text-red-800" : "text-amber-800"}`}>
          <span className="mr-1" aria-hidden>
            {bloquant ? "⛔" : "⚠️"}
          </span>
          {p.message_court}
        </p>
        {p.cible_libelle && <p className="text-xs text-gray-500">{p.cible_libelle}</p>}
      </div>

      {(p.champ || p.correction_proposee) && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 rounded-md bg-gray-50 px-3 py-2 text-xs">
          {p.champ && (
            <>
              <dt className="text-gray-500">{p.champ}</dt>
              <dd className="whitespace-pre-wrap text-gray-800 line-through decoration-red-300">{p.valeur_actuelle ?? "—"}</dd>
            </>
          )}
          {p.correction_proposee && (
            <>
              <dt className="font-medium text-green-700">Proposé</dt>
              <dd className="whitespace-pre-wrap font-medium text-green-800">{p.correction_proposee}</dd>
            </>
          )}
        </dl>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <button type="button" onClick={() => setOuvert((o) => !o)} aria-expanded={ouvert} className="text-xs font-medium text-gray-600 hover:underline">
          {ouvert ? "Masquer ▴" : "Pourquoi ? ▾"}
        </button>
        <div className="flex flex-wrap items-center gap-2">
          {p.valeur_a_appliquer && p.cible_type === "section" && (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => onAppliquer(p)}
              className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              Appliquer
            </button>
          )}
          {p.cible_type === "section" && p.cible && (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => onCorriger(p.cible!)}
              className="rounded-lg border border-indigo-300 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              Corriger →
            </button>
          )}
          {page && (
            <Link to={page.lien} className="rounded-lg border border-indigo-300 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50">
              {page.titre} →
            </Link>
          )}
        </div>
      </div>

      {ouvert && (
        <div className="flex flex-col gap-1 border-t border-gray-100 pt-1.5 text-xs text-gray-700">
          <p>{p.message}</p>
          {p.base_legale && <p className="text-[11px] text-gray-500">{p.base_legale}</p>}
          {reformulation && (
            <div className="rounded bg-gray-50 px-2 py-1.5">
              <p className="text-[11px] font-medium text-gray-500">Proposition conforme</p>
              <p className="select-all whitespace-pre-wrap">{p.reformulation_proposee}</p>
            </div>
          )}
        </div>
      )}
    </li>
  )
}

/**
 * Écran « Vérification finale » des statuts (24/09/2026), affiché quand
 * toutes les sections sont rédigées. Montre les étapes de l'agent de
 * validation (une par tool, dans l'ordre) puis les problèmes, chacun avec un
 * lien : « Corriger → » rouvre la section (le reste du parcours est gardé,
 * retour ici automatique), « Page → » ouvre la page du projet, « Appliquer »
 * enregistre directement une correction certaine. Chaque carte montre le
 * champ, sa valeur actuelle et la correction proposée ; « Pourquoi ? »
 * l'explication et la base légale.
 * « Générer » n'est actif que sans problème bloquant ; des avertissements
 * seuls donnent « Générer quand même ».
 */
export default function StatutsValidationFinaleStep({
  validation,
  isChecking,
  isGenerating,
  onRecheck,
  onCorriger,
  onAppliquer,
  onGenerer,
}: Props) {
  if (validation === null) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">Vérification de vos statuts en cours…</div>
    )
  }
  const bloquants = validation.problemes.filter((p) => p.gravite === "bloquant")
  const avertissements = validation.problemes.filter((p) => p.gravite === "avertissement")
  const toutEstBon = validation.problemes.length === 0

  return (
    <div className="flex flex-col gap-5 rounded-lg border border-gray-200 bg-white p-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Vérification finale</h2>
        <p className="mt-1 text-sm text-gray-600">
          {toutEstBon
            ? "Tout est cohérent. Relisez le document à droite, puis générez vos statuts."
            : bloquants.length > 0
              ? `${bloquants.length} point${bloquants.length > 1 ? "s" : ""} à corriger avant de générer vos statuts.`
              : "Quelques points à vérifier. Vous pouvez les corriger ou générer quand même."}
        </p>
      </div>

      <ol className="flex flex-wrap gap-2">
        {validation.etapes.map((e) => (
          <li key={e.tool} className="flex items-center gap-1.5 rounded-full border border-gray-200 px-2.5 py-1 text-xs text-gray-700">
            <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold ${COULEUR_ETAPE[e.statut]}`}>
              {ICONE_ETAPE[e.statut]}
            </span>
            {e.libelle}
          </li>
        ))}
      </ol>

      {[bloquants, avertissements].map(
        (liste, i) =>
          liste.length > 0 && (
            <ul key={i} className="flex flex-col gap-2">
              {liste.map((p, j) => (
                <ProblemeLigne
                  key={`${p.code}-${j}`}
                  p={p}
                  onCorriger={onCorriger}
                  onAppliquer={onAppliquer}
                  isBusy={isChecking || isGenerating}
                />
              ))}
            </ul>
          ),
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onGenerer}
          disabled={!validation.pret || isGenerating || isChecking}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isGenerating ? "Génération…" : avertissements.length > 0 && validation.pret ? "Générer quand même" : "Générer les statuts"}
        </button>
        {!toutEstBon && (
          <button
            type="button"
            onClick={onRecheck}
            disabled={isChecking || isGenerating}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400 disabled:opacity-50"
          >
            {isChecking ? "Vérification…" : "Vérifier à nouveau"}
          </button>
        )}
      </div>
    </div>
  )
}
