import { useEffect, useRef, useState } from "react"
import type {
  ClauseCandidateRead,
  GuardrailBlockedDetail,
  RegleProbleme,
  SectionAnswerSubmit,
  SectionStateRead,
} from "../../api/documentGenerationApi"
import { Icon, ICON_CHECK, ICON_CHEVRON_LEFT, ICON_DOCUMENT, ICON_INFO, ICON_SKIP, ICON_TAG } from "../pacteFondateursV2/pacteIcons"
import StatutsReglesNotice from "./StatutsReglesNotice"
import StatutsVariableInput from "./StatutsVariableInput"

interface StatutsSectionFormProps {
  section: SectionStateRead
  isSubmitting: boolean
  onSubmit: (body: SectionAnswerSubmit) => void
  onBack: () => void
  /** Bouton "Ne plus inclure cet article" (audit #19) — affiché seulement si
   * `section.article_facultatif_choisi`. */
  onRetirerFacultatif: () => void
  /** Résultat du garde-fou (niveaux A/B) au format `problemes`, ou null.
   * Chaque problème est affiché sous son champ ; un résumé d'une ligne
   * sous le bouton de validation. */
  alerte: GuardrailBlockedDetail | null
  /** « Continuer quand même » (avertissements seuls). */
  onConfirmerAvertissements: () => void
  /** Un champ vient d'être modifié : son erreur disparaît (`associeId` :
   * case d'un associé précis, null = tout le champ). */
  onChampModifie: (nom: string, associeId: string | null) => void
  /** « Revenir à la vérification » pendant une correction (annule). */
  onAnnulerCorrection: () => void
}

/**
 * Fork de `PacteSectionFormV2` (pacteFondateursV2/) pour le service 1.1.4
 * (statuts) — même structure globale (mention_obligatoire/clause_optionnelle/
 * variante_obligatoire, barre de progression, bouton "Précédent"), mais
 * `valeurs` et la validation de complétude sont élargis pour couvrir 2
 * mécanismes du clausier statuts absents (jamais exposés côté frontend
 * jusqu'ici) du pacte :
 *
 * - `auto_identite_associe` DEVIENT une variable éditable quand
 *   `clause.selections_requises[nom]` liste plusieurs candidats (vrai choix,
 *   voir StatutsVariableInput) — l'original v2 exclut TOUT type `auto_*`
 *   de `editableVariables` sans exception, ce qui aurait laissé cette
 *   variable jamais résolue ni jamais demandée.
 * - `texte_par_associe`/`nombre_par_associe` : `valeurs[nom]` n'est plus une
 *   chaîne mais un objet `{ [associateId]: valeur }` — `missingRequired`
 *   doit vérifier une valeur par candidat listé, pas une seule chaîne non
 *   vide.
 *
 * `valeurs` est donc typé `Record<string, string | Record<string, string>>`
 * ici (au lieu de `Record<string, string>` dans l'original) — même
 * élargissement que `SectionAnswerSubmit.valeurs` côté API client.
 */

type ValeursSection = Record<string, string | Record<string, string>>

function inputVariables(clause: ClauseCandidateRead): ClauseCandidateRead["variables_requises"] {
  return clause.variables_requises.filter((v) => v.type !== "reference_croisee")
}

/** Une variable `auto_identite_associe` est éditable seulement si le backend
 * a listé plusieurs candidats pour elle (`selections_requises[nom]`) — sinon
 * elle est résolue automatiquement (0 ou 1 candidat), comme les autres
 * auto_*. Toutes les autres variables `auto_*` restent en lecture seule,
 * jamais "manquantes" au sens de la validation (voir la docstring de
 * `editableVariables` dans PacteSectionFormV2 pour le principe d'origine). */
function editableVariables(clause: ClauseCandidateRead): ClauseCandidateRead["variables_requises"] {
  return inputVariables(clause).filter((v) => {
    if (v.type === "auto_identite_associe") {
      return (clause.selections_requises[v.nom]?.length ?? 0) > 0
    }
    return !v.type.startsWith("auto_")
  })
}

function isMissing(clause: ClauseCandidateRead, v: ClauseCandidateRead["variables_requises"][number], valeurs: ValeursSection): boolean {
  if (v.type === "texte_par_associe" || v.type === "nombre_par_associe") {
    const candidats = clause.selections_requises[v.nom] ?? []
    const saisies = valeurs[v.nom]
    const parAssocie = typeof saisies === "object" && saisies !== null ? saisies : {}
    return candidats.some((c) => !parAssocie[c.id]?.trim())
  }
  const saisie = valeurs[v.nom]
  return typeof saisie !== "string" || !saisie.trim()
}

function ClauseVariableForm({
  clause,
  valeurs,
  onChange,
  problemes,
  noteSiRienASaisir = false,
}: {
  clause: ClauseCandidateRead
  valeurs: ValeursSection
  onChange: (nom: string, value: string | Record<string, string>) => void
  problemes: RegleProbleme[]
  /** Note « Rien à renseigner ici » quand la clause n'a aucun champ.
   * Seulement pour une mention obligatoire : après un choix de l'utilisateur
   * (variante, « Oui, inclure »), la clause n'est pas « automatique » et la
   * note serait trompeuse (retour utilisateur 24/09/2026). */
  noteSiRienASaisir?: boolean
}) {
  // 24/09/2026 (demande utilisateur) : seules les variables à SAISIR sont
  // affichées. Les variables remplies automatiquement (auto_*, déjà résolues
  // depuis le profil/les associés/les dirigeants) ne sont plus montrées en
  // lecture seule — elles surchargeaient la page ; leur valeur reste visible
  // dans l'aperçu PDF à droite. Un choix d'associé parmi plusieurs candidats
  // reste affiché (vraie saisie, voir editableVariables).
  const variables = editableVariables(clause)
  if (variables.length === 0) {
    return noteSiRienASaisir ? (
      <ExplanationBox text="Rien à renseigner ici : cette clause est complétée automatiquement. Relis-la dans l'aperçu à droite avant de valider." />
    ) : null
  }
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-3">
      {variables.map((variable) => (
        <StatutsVariableInput
          key={variable.nom}
          variable={variable}
          value={valeurs[variable.nom] ?? (variable.type === "texte_par_associe" || variable.type === "nombre_par_associe" ? {} : "")}
          onChange={(value) => onChange(variable.nom, value)}
          resolvedValue={clause.valeurs_auto_resolues[variable.nom]}
          candidats={clause.selections_requises[variable.nom]}
          problemes={problemes.filter((p) => p.variable === variable.nom)}
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

function OptionalBadge() {
  return (
    <span className="inline-flex w-fit items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      <Icon path={ICON_TAG} className="h-3 w-3" />
      Optionnelle — tu peux la passer
    </span>
  )
}

/** Audit #19 : article facultatif coché par l'utilisateur sur l'écran de
 * choix — rappel du pourquoi de la question + moyen de revenir sur ce choix. */
function FacultatifChoisiBanner({ isSubmitting, onRetirer }: { isSubmitting: boolean; onRetirer: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-indigo-100 bg-indigo-50 px-3 py-2">
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-700">
        <Icon path={ICON_TAG} className="h-3 w-3" />
        Article facultatif — choisi par vous
      </span>
      <button
        type="button"
        disabled={isSubmitting}
        onClick={onRetirer}
        className="inline-flex items-center gap-1 rounded-md border border-indigo-200 bg-white px-2 py-1 text-xs font-medium text-indigo-700 hover:border-indigo-300 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Icon path={ICON_SKIP} className="h-3 w-3" />
        Ne plus inclure cet article
      </button>
    </div>
  )
}

function ExplanationBox({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm text-blue-800">
      <Icon path={ICON_INFO} className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
      <p>{text}</p>
    </div>
  )
}

export default function StatutsSectionForm({
  section,
  isSubmitting,
  onSubmit,
  onBack,
  onRetirerFacultatif,
  alerte,
  onConfirmerAvertissements,
  onChampModifie,
  onAnnulerCorrection,
}: StatutsSectionFormProps) {
  const precedente = section.reponse_precedente as
    | { inclus?: boolean; variante?: string; code_clause?: string; valeurs?: ValeursSection }
    | null

  const [valeurs, setValeurs] = useState<ValeursSection>(() => precedente?.valeurs ?? {})
  // Section de base d'un article facultatif coché (audit #19) : déjà choisie
  // sur l'écran de choix, on ne redemande pas "l'inclure ?".
  const estBaseFacultatifChoisi = !!section.section_de_base_facultatif
  const [inclusChoice, setInclusChoice] = useState<boolean | null>(() =>
    estBaseFacultatifChoisi ? true : (precedente?.inclus ?? null),
  )
  const [selectedVariante, setSelectedVariante] = useState<string | null>(() => precedente?.variante ?? null)
  const [selectedSousVariante, setSelectedSousVariante] = useState<string | null>(() =>
    precedente && precedente.code_clause && precedente.code_clause !== precedente.variante
      ? precedente.code_clause
      : null,
  )

  const problemes = alerte?.problemes ?? []
  const racineRef = useRef<HTMLDivElement | null>(null)

  function setValeur(nom: string, value: string | Record<string, string>) {
    if (typeof value === "object") {
      // Saisie par associé : seule la case modifiée perd son erreur.
      const avant = valeurs[nom]
      const ancien = typeof avant === "object" && avant !== null ? avant : {}
      Object.keys(value)
        .filter((id) => value[id] !== ancien[id])
        .forEach((id) => onChampModifie(nom, id))
    } else {
      onChampModifie(nom, null)
    }
    setValeurs((prev) => ({ ...prev, [nom]: value }))
  }

  /** Défile jusqu'au premier champ en faute (ordre d'affichage) et y place
   * le curseur. */
  function allerAuPremier() {
    const racine = racineRef.current
    if (!racine || problemes.length === 0) return
    const champ = Array.from(racine.querySelectorAll<HTMLElement>("[data-champ]")).find((el) =>
      problemes.some((p) => p.variable === el.dataset.champ),
    )
    if (!champ) return
    const probleme = problemes.find((p) => p.variable === champ.dataset.champ)
    const cible =
      (probleme?.associe_id && champ.querySelector<HTMLElement>(`[data-champ-associe="${probleme.associe_id}"]`)) || champ
    cible.scrollIntoView({ behavior: "smooth", block: "center" })
    cible.querySelector<HTMLElement>("input, textarea, select")?.focus({ preventScroll: true })
  }

  // Défilement seulement quand une NOUVELLE réponse du serveur arrive (la
  // page remet l'alerte à null à chaque envoi) -- jamais quand une erreur
  // disparaît parce que l'utilisateur corrige un champ (sinon la page
  // sauterait pendant la frappe).
  const alerteAvant = useRef<GuardrailBlockedDetail | null>(null)
  useEffect(() => {
    if (alerte && !alerteAvant.current) allerAuPremier()
    alerteAvant.current = alerte
  }, [alerte])

  /** Résumé sous le bouton ; les problèmes dont le champ n'est pas affiché
   * (cas défensif) y sont détaillés pour ne jamais être perdus. */
  function resume(clause: ClauseCandidateRead | null) {
    if (!alerte || problemes.length === 0) return null
    const affiches = new Set(clause ? editableVariables(clause).map((v) => v.nom) : [])
    return (
      <StatutsReglesNotice
        detail={alerte}
        problemesHorsChamp={problemes.filter((p) => !affiches.has(p.variable))}
        isSubmitting={isSubmitting}
        onConfirmer={onConfirmerAvertissements}
        onAllerAuPremier={allerAuPremier}
      />
    )
  }

  function missingRequired(clause: ClauseCandidateRead): boolean {
    return editableVariables(clause).some((v) => isMissing(clause, v, valeurs))
  }

  const isOptional =
    !estBaseFacultatifChoisi &&
    (section.comportement_section === "clause_optionnelle" ||
      (section.comportement_section === "variante_obligatoire" && section.obligatoire === false))

  // Pendant une correction, « Section précédente » effacerait toutes les
  // réponses suivantes : remplacé par le bandeau « Revenir à la vérification ».
  const enCorrection = !!section.correction_en_cours
  const bandeauCorrection = enCorrection && (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2">
      <span className="text-xs font-medium text-indigo-800">✏️ Correction depuis la vérification finale</span>
      <button
        type="button"
        disabled={isSubmitting}
        onClick={onAnnulerCorrection}
        className="rounded-md border border-indigo-200 bg-white px-2 py-1 text-xs font-medium text-indigo-700 hover:border-indigo-300 disabled:opacity-50"
      >
        ↩ Revenir à la vérification
      </button>
    </div>
  )

  const backButton = !enCorrection && section.position !== null && section.position > 1 && (
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
      {bandeauCorrection}
      {backButton}
      <ProgressBar position={section.position} total={section.total_sections_estime} />
      {section.article_facultatif_choisi && (
        <FacultatifChoisiBanner isSubmitting={isSubmitting} onRetirer={onRetirerFacultatif} />
      )}
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
      <div ref={racineRef} className="flex flex-col gap-4">
        {header}
        <ClauseVariableForm clause={clause} valeurs={valeurs} onChange={setValeur} problemes={problemes} noteSiRienASaisir />
        <button
          type="button"
          disabled={isSubmitting || missingRequired(clause)}
          onClick={() => onSubmit({ valeurs })}
          className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Icon path={ICON_CHECK} className="h-4 w-4" />
          Valider cette section
        </button>
        {resume(clause)}
      </div>
    )
  }

  if (section.comportement_section === "clause_optionnelle" && section.clause) {
    const clause = section.clause
    // Clause sans champ à saisir : « Oui, inclure » suffit, pas de second
    // clic sur « Valider » (retour utilisateur 24/09/2026).
    const sansChamp = editableVariables(clause).length === 0
    return (
      <div ref={racineRef} className="flex flex-col gap-4">
        {header}
        {!estBaseFacultatifChoisi && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => {
              setInclusChoice(true)
              if (sansChamp) onSubmit({ inclus: true, valeurs: {} })
            }}
            disabled={isSubmitting}
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
        )}

        {/* Sans champ : bouton masqué pendant l'envoi automatique ; il
            réapparaît si l'envoi échoue, au retour sur cette section, ou pour
            un facultatif déjà choisi (pas de bouton « Oui » dans ce cas). */}
        {inclusChoice === true && (!sansChamp || !isSubmitting) && (
          <>
            <ClauseVariableForm clause={clause} valeurs={valeurs} onChange={setValeur} problemes={problemes} />
            <button
              type="button"
              disabled={isSubmitting || missingRequired(clause)}
              onClick={() => onSubmit({ inclus: true, valeurs })}
              className="inline-flex w-fit items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Icon path={ICON_CHECK} className="h-4 w-4" />
              Valider cette clause
            </button>
            {resume(clause)}
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
      <div ref={racineRef} className="flex flex-col gap-4">
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

        {/* Pas de rappel de la description sous le choix : elle est déjà
            dans la carte sélectionnée (redondance, retour utilisateur). */}
        {sousClause && (
          <ClauseVariableForm clause={sousClause} valeurs={valeurs} onChange={setValeur} problemes={problemes} />
        )}

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
          {!section.obligatoire && !estBaseFacultatifChoisi && (
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
        {resume(sousClause)}
      </div>
    )
  }

  return <div className="text-sm text-gray-500">Type de section non pris en charge : {section.comportement_section}</div>
}
