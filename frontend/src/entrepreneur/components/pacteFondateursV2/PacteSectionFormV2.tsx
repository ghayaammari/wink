import { useState } from "react"
import type {
  ClauseCandidateRead,
  SectionAnswerSubmit,
  SectionStateRead,
} from "../../api/documentGenerationApi"
import PacteVariableInputV2 from "./PacteVariableInputV2"
import { Icon, ICON_CHECK, ICON_CHEVRON_LEFT, ICON_DOCUMENT, ICON_INFO, ICON_SKIP, ICON_TAG } from "./pacteIcons"

interface PacteSectionFormV2Props {
  section: SectionStateRead
  isSubmitting: boolean
  onSubmit: (body: SectionAnswerSubmit) => void
  /** Revenir à la dernière section interactive répondue (24/09/2026) — absent
   * de bouton si `section.position` est déjà 1 (rien avant), voir plus bas. */
  onBack: () => void
}

/**
 * Fork v2 de `PacteSectionForm` (pacteFondateurs/) — identique en tout point,
 * sauf `ClauseVariableForm` qui rend `PacteVariableInputV2` (radio pour
 * `choix`) au lieu de `PacteVariableInput`. L'original v1 n'est pas touché
 * (même règle que PacteVariableInputV2 — voir sa docstring).
 *
 * AJOUTS 24/09/2026 (demande utilisateur) : bouton "Précédent" + barre de
 * progression (position/total_sections_estime, voir SectionStateRead), titre
 * "Article X — Nom de la clause" au lieu du seul nom de clause
 * (`section.nom_article`), un message explicite pour les clauses sans aucune
 * variable à saisir, un badge "Optionnelle" affiché DÈS l'en-tête (avant, il
 * fallait dérouler jusqu'au bouton "Passer" pour comprendre que la section
 * n'était pas obligatoire), et des icônes cohérentes (style Heroicons outline,
 * même convention que IconActionButton.tsx) plutôt que des caractères ASCII
 * ("◀") ou du texte seul pour les actions.
 */

function inputVariables(clause: ClauseCandidateRead): ClauseCandidateRead["variables_requises"] {
  return clause.variables_requises.filter((v) => v.type !== "reference_croisee")
}

/** Sous-ensemble RÉELLEMENT saisi par l'utilisateur — exclut aussi les types
 * `auto_*` (24/09/2026) : ces variables se rendent en lecture seule
 * (PacteVariableInputV2) et sont résolues côté backend, jamais "manquantes"
 * au sens où l'utilisateur devrait les remplir. Une donnée source absente
 * (ProjectLegalProfile incomplet) affiche "(non renseigné)" mais ne bloque
 * jamais "Valider cette section" — décision actée le 24/09/2026 : cohérent
 * avec le reste de l'app (placeholder visible plutôt que blocage). */
function editableVariables(clause: ClauseCandidateRead): ClauseCandidateRead["variables_requises"] {
  return inputVariables(clause).filter((v) => !v.type.startsWith("auto_"))
}

function ClauseVariableForm({
  clause,
  valeurs,
  onChange,
}: {
  clause: ClauseCandidateRead
  valeurs: Record<string, string>
  onChange: (nom: string, value: string) => void
}) {
  const variables = inputVariables(clause)
  if (variables.length === 0) {
    // 24/09/2026 : avant, cette clause ne rendait RIEN ici (juste le titre +
    // le bouton "Valider" plus haut/bas dans le formulaire) — l'utilisateur
    // ne pouvait pas savoir si c'était normal ou un bug. Ce n'en est pas un :
    // certaines clauses (ex. chapeaux d'article) sont un texte fixe, sans
    // aucune information à saisir — le dire explicitement plutôt que de
    // laisser un vide.
    return (
      <ExplanationBox text="Cette clause est un texte fixe — rien à renseigner ici. Relis-la dans l'aperçu à droite avant de valider." />
    )
  }
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-3">
      {variables.map((variable) => (
        <PacteVariableInputV2
          key={variable.nom}
          variable={variable}
          value={valeurs[variable.nom] ?? ""}
          onChange={(value) => onChange(variable.nom, value)}
          resolvedValue={clause.valeurs_auto_resolues[variable.nom]}
        />
      ))}
    </div>
  )
}

function ProgressBar({ position, total }: { position: number | null; total: number }) {
  if (position === null || total <= 0) return null
  const pct = Math.min(100, Math.round((position / total) * 100))
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>
          Section {position} / {total}
        </span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
        <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

/** Badge "Optionnelle" — affiché dès l'en-tête (24/09/2026, demande
 * utilisateur : l'utilisateur ne devait pas avoir à dérouler jusqu'au bouton
 * "Passer" pour comprendre qu'une section n'est pas obligatoire). Ambre
 * plutôt que rouge/gris : signale une information neutre ("tu as le choix"),
 * pas un avertissement. Aucun badge pour une section obligatoire — le
 * silence est la valeur par défaut, pas la peine de le dire à chaque fois. */
function OptionalBadge() {
  return (
    <span className="inline-flex w-fit items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Icon path={ICON_TAG} className="h-3 w-3" />
      Optionnelle — tu peux la passer
    </span>
  )
}

/** Explication d'une clause (`description_clause`) — service 1.1.13, "3a"
 * (25/09/2026, demande utilisateur) : avant, ce texte était un <p> gris,
 * visuellement indissociable d'un sous-titre. Ici mis en évidence comme un
 * vrai bloc d'explication (même langage visuel que le message "clause
 * fixe" plus bas) pour répondre au constat de l'utilisateur : un
 * entrepreneur novice ne comprend pas toujours POURQUOI il remplit telle
 * clause. Explication statique pré-rédigée, pas d'appel LLM — dette
 * assumée : ne répond pas aux questions ad-hoc ("quelle valeur mettre"),
 * seulement au "pourquoi cette clause existe". Voir échange avec
 * l'utilisateur sur l'agent conversationnel (catégorie 3b, différé). */
function ExplanationBox({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
      <Icon path={ICON_INFO} className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
      <p>{text}</p>
    </div>
  )
}

export default function PacteSectionFormV2({ section, isSubmitting, onSubmit, onBack }: PacteSectionFormV2Props) {
  const precedente = section.reponse_precedente as
    | { inclus?: boolean; variante?: string; code_clause?: string; valeurs?: Record<string, string> }
    | null

  const [valeurs, setValeurs] = useState<Record<string, string>>(() => precedente?.valeurs ?? {})
  const [inclusChoice, setInclusChoice] = useState<boolean | null>(() => precedente?.inclus ?? null)
  const [selectedVariante, setSelectedVariante] = useState<string | null>(() => precedente?.variante ?? null)
  const [selectedSousVariante, setSelectedSousVariante] = useState<string | null>(() =>
    precedente && precedente.code_clause && precedente.code_clause !== precedente.variante
      ? precedente.code_clause
      : null,
  )

  function setValeur(nom: string, value: string) {
    setValeurs((prev) => ({ ...prev, [nom]: value }))
  }

  function missingRequired(clause: ClauseCandidateRead): boolean {
    return editableVariables(clause).some((v) => !valeurs[v.nom]?.trim())
  }

  const isOptional =
    section.comportement_section === "clause_optionnelle" ||
    (section.comportement_section === "variante_obligatoire" && section.obligatoire === false)

  const backButton = section.position !== null && section.position > 1 && (
    <button
      type="button"
      disabled={isSubmitting}
      onClick={onBack}
      className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:border-gray-400 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Icon path={ICON_CHEVRON_LEFT} className="h-3.5 w-3.5" />
      Section précédente
    </button>
  )

  const header = (
    <div className="flex flex-col gap-2">
      {backButton}
      <ProgressBar position={section.position} total={section.total_sections_estime} />
      <div className="flex flex-col gap-1.5">
        {section.nom_article && section.nom_article !== section.titre_section && (
          <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-gray-700">
            <Icon path={ICON_DOCUMENT} className="h-3.5 w-3.5 text-gray-500" />
            {section.nom_article}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold text-gray-900">
            {section.titre_section ?? section.code_section}
          </h2>
          {isOptional && <OptionalBadge />}
        </div>
        {section.explication_section && <ExplanationBox text={section.explication_section} />}
      </div>
    </div>
  )

  if (section.comportement_section === "mention_obligatoire" && section.clause) {
    const clause = section.clause
    return (
      <div className="flex flex-col gap-4">
        {header}
        <ClauseVariableForm clause={clause} valeurs={valeurs} onChange={setValeur} />
        <button
          type="button"
          disabled={isSubmitting || missingRequired(clause)}
          onClick={() => onSubmit({ valeurs })}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Icon path={ICON_CHECK} className="h-4 w-4" />
          Valider cette section
        </button>
      </div>
    )
  }

  if (section.comportement_section === "clause_optionnelle" && section.clause) {
    const clause = section.clause
    return (
      <div className="flex flex-col gap-4">
        {header}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setInclusChoice(true)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-medium ${
              inclusChoice === true
                ? "border-indigo-500 bg-indigo-50 text-indigo-700"
                : "border-gray-300 text-gray-700 hover:border-gray-400"
            }`}
          >
            <Icon path={ICON_CHECK} className="h-4 w-4" />
            Oui, inclure cette clause
          </button>
          <button
            type="button"
            onClick={() => {
              setInclusChoice(false)
              onSubmit({ inclus: false })
            }}
            disabled={isSubmitting}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-4 py-2 text-sm font-medium ${
              inclusChoice === false
                ? "border-amber-400 bg-amber-50 text-amber-700"
                : "border-gray-300 text-gray-700 hover:border-gray-400"
            }`}
          >
            <Icon path={ICON_SKIP} className="h-4 w-4" />
            Passer (ne pas inclure cette clause)
          </button>
        </div>

        {inclusChoice === true && (
          <>
            <ClauseVariableForm clause={clause} valeurs={valeurs} onChange={setValeur} />
            <button
              type="button"
              disabled={isSubmitting || missingRequired(clause)}
              onClick={() => onSubmit({ inclus: true, valeurs })}
              className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon path={ICON_CHECK} className="h-4 w-4" />
              Valider cette clause
            </button>
          </>
        )}
      </div>
    )
  }

  if (section.comportement_section === "variante_obligatoire") {
    const candidats = section.candidats ?? []
    const candidat = candidats.find((c) => c.code_clause === selectedVariante) ?? null
    const hasSousCandidats = !!candidat?.sous_candidats?.length
    const sousClause = hasSousCandidats
      ? candidat!.sous_candidats!.find((s) => s.code_clause === selectedSousVariante) ?? null
      : candidat
    const canSubmit = candidat !== null && (!hasSousCandidats || sousClause !== null)

    return (
      <div className="flex flex-col gap-4">
        {header}
        <div className="flex flex-col gap-2">
          {candidats.map((c) => (
            <button
              key={c.code_clause}
              type="button"
              onClick={() => {
                setSelectedVariante(c.code_clause)
                setSelectedSousVariante(null)
                setValeurs({})
              }}
              className={`flex flex-col gap-0.5 rounded-lg border p-3 text-left ${
                selectedVariante === c.code_clause
                  ? "border-indigo-500 bg-indigo-50"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <span className="text-sm font-medium text-gray-900">{c.titre_clause}</span>
              <span className="text-xs text-gray-600">{c.description_clause}</span>
            </button>
          ))}
        </div>

        {hasSousCandidats && (
          <div className="flex flex-col gap-2 pl-4">
            {candidat!.sous_candidats!.map((sous) => (
              <button
                key={sous.code_clause}
                type="button"
                onClick={() => {
                  setSelectedSousVariante(sous.code_clause)
                  setValeurs({})
                }}
                className={`flex flex-col gap-0.5 rounded-lg border p-3 text-left ${
                  selectedSousVariante === sous.code_clause
                    ? "border-indigo-500 bg-indigo-50"
                    : "border-gray-300 hover:border-gray-400"
                }`}
              >
                <span className="text-sm font-medium text-gray-900">{sous.titre_clause}</span>
                <span className="text-xs text-gray-600">{sous.description_clause}</span>
              </button>
            ))}
          </div>
        )}

        {sousClause && sousClause.description_clause && (
          <ExplanationBox text={sousClause.description_clause} />
        )}
        {sousClause && <ClauseVariableForm clause={sousClause} valeurs={valeurs} onChange={setValeur} />}

        <div className="flex gap-2">
          <button
            type="button"
            disabled={isSubmitting || !canSubmit || (sousClause ? missingRequired(sousClause) : true)}
            onClick={() =>
              candidat &&
              onSubmit({
                variante: candidat.code_clause,
                sous_variante: selectedSousVariante ?? undefined,
                valeurs,
              })
            }
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Icon path={ICON_CHECK} className="h-4 w-4" />
            Valider ce choix
          </button>
          {!section.obligatoire && (
            <button
              type="button"
              disabled={isSubmitting}
              onClick={() => onSubmit({})}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
            >
              <Icon path={ICON_SKIP} className="h-4 w-4" />
              Passer (aucune de ces clauses)
            </button>
          )}
        </div>
      </div>
    )
  }

  return <div className="text-sm text-gray-500">Type de section non pris en charge : {section.comportement_section}</div>
}
