import { type ChangeEvent, useEffect, useRef, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyResearcherProfile } from "../api/researcherProfileApi"
import {
  depositWork,
  deleteWork,
  listMyWorks,
  regenerateAnalysis,
  triggerExtraction,
  validateField,
  type FieldValue,
  type PublicationType,
  type ResearchWork,
} from "../api/researchWorkApi"

const SOURCE_LABELS: Record<ResearchWork["source_type"], string> = {
  extrait_hal_openalex: "Extrait automatiquement",
  depot_manuel: "Déposé manuellement",
}

const WORK_STATUS_LABELS: Record<ResearchWork["validation_status"], string> = {
  pending_confirmation: "En attente de validation",
  confirmed: "Confirmé",
  rejected: "Rejeté",
}

const FIELD_NAME_LABELS: Record<string, string> = {
  title: "Titre",
  abstract: "Résumé",
  authors: "Auteurs",
  venue: "Revue / conférence",
  doi: "DOI",
  publication_type: "Type de publication",
  paper_summary: "Résumé (généré)",
  methodology: "Méthodologie (généré)",
  key_findings: "Résultats clés (généré)",
  application_domains: "Domaine d'application (généré)",
}

// Ordre d'affichage fixe des champs, aligné sur l'ordre de lecture initial
// (titre en en-tête, résumé, puis le dl Auteurs/Revue/DOI/Type, puis les
// champs générés) — sans ça, l'ordre suit celui renvoyé par le backend
// (insertion dans generated_field_values), qui ne correspond à rien de
// stable ni de lisible pour le chercheur.
const FIELD_DISPLAY_ORDER = Object.keys(FIELD_NAME_LABELS)

function sortFieldGroups<T extends readonly [string, FieldValue[]]>(groups: T[]): T[] {
  return [...groups].sort((a, b) => {
    const indexA = FIELD_DISPLAY_ORDER.indexOf(a[0])
    const indexB = FIELD_DISPLAY_ORDER.indexOf(b[0])
    return (indexA === -1 ? FIELD_DISPLAY_ORDER.length : indexA) - (indexB === -1 ? FIELD_DISPLAY_ORDER.length : indexB)
  })
}

const PUBLICATION_TYPES: { value: PublicationType; label: string }[] = [
  { value: "article", label: "Article" },
  { value: "communication", label: "Communication" },
  { value: "these", label: "Thèse" },
  { value: "brevet", label: "Brevet" },
  { value: "rapport", label: "Rapport" },
]

const PUBLICATION_TYPE_LABELS: Record<PublicationType, string> = {
  article: "Article",
  communication: "Communication",
  these: "Thèse",
  brevet: "Brevet",
  rapport: "Rapport",
}

// Duplication assumée avec SINGLE_VALUE_FIELDS côté backend
// (researcher_field_value_service.py) — pas de schéma partagé front/back en
// I0. À revoir si cette liste évolue souvent ou si un 3e acteur en a besoin.
const MULTI_VALUE_FIELD_NAMES = new Set(["application_domains", "research_domains", "authors"])

// Champs factuels (titre, auteurs, venue, doi, type) — désormais validés via
// researcher_field_values comme les champs générés, mais déjà affichés une
// fois dans le bloc de lecture principal (dl "Auteurs/Revue/DOI/Type" +
// titre en en-tête). En dehors du mode révision, on les exclut de la liste
// de cards pour éviter un doublon d'affichage — ils n'y réapparaissent qu'en
// mode révision, là où on les modifie/confirme désormais.
const DIRECT_FIELD_NAMES = new Set(["title", "abstract", "authors", "venue", "doi", "publication_type"])

function formatFieldValue(fieldName: string, value: string): string {
  if (fieldName === "publication_type") {
    return PUBLICATION_TYPE_LABELS[value as PublicationType] ?? value
  }
  return value
}

const POLL_INTERVAL_MS = 3000
// Le dépôt manuel = un seul appel LLM, quelques secondes suffisent. L'extraction
// HAL/OpenAlex peut traiter des dizaines de papiers en série (appel LLM + pause
// anti rate-limit à chaque fois, voir research_extraction_service) — largement
// au-delà de 90s pour un chercheur avec beaucoup de publications.
const POLL_TIMEOUT_MS: Record<PendingJob["type"], number> = {
  deposit: 90000,
  extraction: 600000,
}

type ValidateAction = "confirm" | "reject" | "edit"

type PendingJob = {
  type: "deposit" | "extraction"
  status: "processing" | "failed"
}

const PENDING_JOB_LABELS: Record<PendingJob["type"], { processing: string; failed: string }> = {
  deposit: {
    processing: "Extraction en cours... la card apparaîtra automatiquement une fois le traitement terminé.",
    failed: "L'extraction prend plus de temps que prévu ou a échoué. Réessaie le dépôt.",
  },
  extraction: {
    // Le polling attend maintenant profile.sync_status === "completed", pas
    // "un travail est apparu" — les travaux s'affichent au fur et à mesure
    // (research_extraction_service commit chacun individuellement) sans que
    // ça ferme le bandeau avant que tout soit vraiment fini.
    processing: "Extraction HAL/OpenAlex en cours... tes travaux apparaîtront ici au fur et à mesure.",
    failed: "L'extraction prend plus de temps que prévu ou a échoué. Réessaie, ou vérifie ton ORCID dans ton profil.",
  },
}

function groupByFieldName(values: FieldValue[]): Map<string, FieldValue[]> {
  const groups = new Map<string, FieldValue[]>()
  for (const value of values) {
    const existing = groups.get(value.field_name) ?? []
    existing.push(value)
    groups.set(value.field_name, existing)
  }
  return groups
}

/**
 * "Mes travaux" — service 0.0.2 (dépôt, extraction async) + 0.0.3
 * (consultation). Le dépôt ne demande que le fichier ; le backend crée le
 * research_work en tâche de fond une fois l'extraction terminée (pas de
 * ligne DB tant que ce n'est pas fini — voir research_extraction_service).
 * Le composant affiche donc un placeholder purement local pendant l'attente,
 * et détecte la fin du traitement par polling de la liste.
 */
export default function ResearchWorksPage() {
  const { accessToken } = useAuth()
  const [works, setWorks] = useState<ResearchWork[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pendingJob, setPendingJob] = useState<PendingJob | null>(null)
  const pollTimer = useRef<number | null>(null)
  const pollDeadline = useRef<number>(0)

  function loadWorks(): Promise<ResearchWork[]> {
    if (!accessToken) return Promise.resolve([])
    return listMyWorks(accessToken).then((data) => {
      setWorks(data)
      return data
    })
  }

  useEffect(() => {
    loadWorks().catch((err) => setError(err instanceof ApiError ? err.message : "Impossible de charger tes travaux."))
    return () => stopPolling()
  }, [accessToken])

  function stopPolling() {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
  }

  function startPolling(knownIds: Set<string>, jobType: PendingJob["type"]) {
    pollDeadline.current = Date.now() + POLL_TIMEOUT_MS[jobType]

    const poll = () => {
      if (Date.now() > pollDeadline.current) {
        setPendingJob({ type: jobType, status: "failed" })
        stopPolling()
        return
      }

      loadWorks()
        .then(async (data) => {
          if (jobType === "deposit") {
            // Un seul travail attendu pour un dépôt manuel — "un nouveau
            // travail est apparu" est un signal de fin fiable ici.
            if (data.some((w) => !knownIds.has(w.id))) {
              setPendingJob(null)
              stopPolling()
              return
            }
            pollTimer.current = window.setTimeout(poll, POLL_INTERVAL_MS)
            return
          }

          // Extraction : peut créer plusieurs travaux, déjà rechargés
          // ci-dessus au fur et à mesure par loadWorks(). Le signal de fin
          // exact est sync_status — "un travail est apparu" ne suffit plus
          // à savoir si TOUS sont traités.
          if (!accessToken) return
          const profile = await getMyResearcherProfile(accessToken)
          if (profile.sync_status === "completed") {
            setPendingJob(null)
            stopPolling()
          } else if (profile.sync_status === "failed") {
            setPendingJob({ type: jobType, status: "failed" })
            stopPolling()
          } else {
            pollTimer.current = window.setTimeout(poll, POLL_INTERVAL_MS)
          }
        })
        .catch(() => {
          // erreur réseau ponctuelle pendant le polling — on retente plutôt que d'abandonner tout de suite
          pollTimer.current = window.setTimeout(poll, POLL_INTERVAL_MS)
        })
    }

    pollTimer.current = window.setTimeout(poll, POLL_INTERVAL_MS)
  }

  async function handleFileSelected(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = "" // permet de redéposer le même fichier deux fois de suite
    if (!file || !accessToken) return

    setError(null)
    setPendingJob({ type: "deposit", status: "processing" })
    const knownIds = new Set((works ?? []).map((w) => w.id))

    try {
      await depositWork(accessToken, file)
      startPolling(knownIds, "deposit")
    } catch (err) {
      setPendingJob(null)
      setError(err instanceof ApiError ? err.message : "Le dépôt a échoué.")
    }
  }

  async function handleTriggerExtraction() {
    if (!accessToken) return

    setError(null)
    setPendingJob({ type: "extraction", status: "processing" })
    const knownIds = new Set((works ?? []).map((w) => w.id))

    try {
      await triggerExtraction(accessToken)
      startPolling(knownIds, "extraction")
    } catch (err) {
      setPendingJob(null)
      setError(err instanceof ApiError ? err.message : "Le lancement de l'extraction a échoué.")
    }
  }

  async function handleValidate(fieldValueId: string, action: ValidateAction, newValue?: string) {
    if (!accessToken) return
    try {
      await validateField(accessToken, fieldValueId, action, newValue)
      loadWorks()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La validation a échoué.")
    }
  }

  async function handleDeleteWork(workId: string) {
    if (!accessToken) return
    try {
      await deleteWork(accessToken, workId)
      setWorks((prev) => (prev ? prev.filter((w) => w.id !== workId) : prev))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La suppression a échoué.")
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!works) return <p className="text-sm text-gray-500">Chargement...</p>

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Mes travaux</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleTriggerExtraction}
            disabled={pendingJob?.type === "extraction" && pendingJob.status === "processing"}
            className="rounded-lg border border-indigo-600 px-3 py-2 text-sm font-medium text-indigo-600 transition hover:bg-indigo-50 disabled:opacity-50"
          >
            Extraire depuis HAL/OpenAlex
          </button>
          <label className="cursor-pointer rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700">
            Déposer un travail
            <input type="file" accept="application/pdf" className="hidden" onChange={handleFileSelected} />
          </label>
        </div>
      </div>

      {pendingJob?.status === "processing" && (
        <div className="rounded-lg border border-dashed border-indigo-300 bg-indigo-50 p-4 text-sm text-indigo-700">
          {PENDING_JOB_LABELS[pendingJob.type].processing}
        </div>
      )}
      {pendingJob?.status === "failed" && (
        <div className="rounded-lg border border-dashed border-red-300 bg-red-50 p-4 text-sm text-red-700">
          {PENDING_JOB_LABELS[pendingJob.type].failed}
          <button type="button" onClick={() => setPendingJob(null)} className="ml-2 underline">
            Fermer
          </button>
        </div>
      )}

      {works.length === 0 && !pendingJob && (
        <p className="text-sm text-gray-500">Aucun travail pour l'instant — dépose ton premier travail ci-dessus.</p>
      )}

      <div className="flex flex-col gap-3">
        {works.map((work) => (
          <WorkCard
            key={work.id}
            work={work}
            onValidate={handleValidate}
            onDelete={handleDeleteWork}
            onReload={() => loadWorks().catch(() => {})}
          />
        ))}
      </div>
    </div>
  )
}

interface WorkCardProps {
  work: ResearchWork
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
  onDelete: (workId: string) => void
  onReload: () => void
}

function WorkCard({ work, onValidate, onDelete, onReload }: WorkCardProps) {
  const [isOpen, setIsOpen] = useState(false)
  const pendingCount = work.generated_field_values.filter(
    (f) => f.validation_status === "pending_confirmation",
  ).length

  return (
    <section className="rounded-lg border border-gray-200 bg-white">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <h2 className="text-sm font-semibold text-gray-900">{work.title}</h2>
        <div className="flex shrink-0 items-center gap-2">
          {pendingCount > 0 && (
            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
              {pendingCount} à valider
            </span>
          )}
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              work.validation_status === "confirmed"
                ? "bg-green-50 text-green-700"
                : work.validation_status === "rejected"
                  ? "bg-red-50 text-red-700"
                  : "bg-amber-50 text-amber-700"
            }`}
          >
            {WORK_STATUS_LABELS[work.validation_status]}
          </span>
          <span className="text-gray-400">{isOpen ? "▲" : "▼"}</span>
        </div>
      </button>

      {isOpen && (
        <div className="border-t border-gray-100 p-4">
          <WorkDetails work={work} onValidate={onValidate} onDelete={onDelete} onReload={onReload} />
        </div>
      )}
    </section>
  )
}

interface WorkDetailsProps {
  work: ResearchWork
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
  onDelete: (workId: string) => void
  onReload: () => void
}

function WorkDetails({ work, onValidate, onDelete, onReload }: WorkDetailsProps) {
  const [mode, setMode] = useState<"closed" | "review" | "edit">("closed")
  const [isDeleting, setIsDeleting] = useState(false)

  function handleDeleteClick() {
    // Confirmation native simple — suffisant pour une action destructrice
    // ponctuelle en I0 ; une vraie modale n'apporterait rien de plus ici.
    if (window.confirm(`Supprimer définitivement "${work.title}" ? Cette action est irréversible.`)) {
      setIsDeleting(true)
      onDelete(work.id)
    }
  }

  // Tous les champs validés — générés (paper_summary...) ET désormais
  // factuels (titre, auteurs, venue, doi, type), rejetés exclus. Un rejeté
  // n'existe plus visuellement nulle part une fois traité, filtré ici une
  // seule fois en amont plutôt que dupliqué dans chaque sous-composant.
  const allFieldGroups = sortFieldGroups(
    Array.from(groupByFieldName(work.generated_field_values))
      .map(([fieldName, values]) => [fieldName, values.filter((v) => v.validation_status !== "rejected")] as const)
      .filter(([, values]) => values.length > 0),
  )

  // Hors mode révision, les champs factuels sont déjà affichés une fois
  // au-dessus (titre en en-tête, dl Auteurs/Revue/DOI/Type) — les exclure
  // ici évite un doublon. Ils ne réapparaissent qu'en révision, là où on
  // les modifie/confirme désormais (plus de formulaire séparé).
  const readOnlyFieldGroups = allFieldGroups.filter(([fieldName]) => !DIRECT_FIELD_NAMES.has(fieldName))

  const pendingFieldsCount = work.generated_field_values.filter(
    (f) => f.validation_status === "pending_confirmation",
  ).length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
          {SOURCE_LABELS[work.source_type]}
        </span>
        <div className="flex items-center gap-3">
          {mode !== "closed" ? (
            <button type="button" onClick={() => setMode("closed")} className="text-xs font-medium text-indigo-600">
              Terminer
            </button>
          ) : (
            <>
              {/* Visible seulement s'il y a des champs en attente — mène au
                  mode "review" (Confirmer/Rejeter/Modifier par champ). */}
              {pendingFieldsCount > 0 && (
                <button
                  type="button"
                  onClick={() => setMode("review")}
                  className="text-xs font-medium text-amber-700"
                >
                  Consulter les champs à valider ({pendingFieldsCount})
                </button>
              )}
              {/* Mène au mode "edit" : tous les champs directement éditables
                  (input/textarea + Enregistrer), sans Confirmer/Rejeter —
                  pour corriger une valeur sans passer par le workflow de
                  validation. */}
              <button
                type="button"
                onClick={() => setMode("edit")}
                className="text-xs font-medium text-indigo-600"
              >
                Modifier
              </button>
            </>
          )}
          <button
            type="button"
            onClick={handleDeleteClick}
            disabled={isDeleting}
            className="text-xs font-medium text-red-600 disabled:opacity-50"
          >
            {isDeleting ? "Suppression..." : "Supprimer"}
          </button>
        </div>
      </div>

      {/* Masqué en mode révision : les mêmes infos (résumé, auteurs, venue,
          DOI, type) réapparaissent plus bas sous forme de cards éditables
          avec Confirmer/Rejeter/Modifier — les afficher aussi ici ferait
          doublon et forcerait à faire défiler deux fois la même info. */}
      {mode === "closed" && (
        <>
          {work.abstract && <p className="text-sm text-gray-600">{work.abstract}</p>}

          {/* Titre, auteurs, venue, DOI, type sont maintenant des attributs
              validés (voir researcher_field_value_service.SINGLE_VALUE_FIELDS) —
              ce bloc affiche leur valeur matérialisée actuelle ; leur édition se
              fait désormais via les cards de révision plus bas, plus de
              formulaire libre séparé. */}
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-gray-600">
            <div>
              <dt className="font-medium text-gray-500">Auteurs</dt>
              <dd>{work.authors?.length ? work.authors.join(", ") : "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-gray-500">Revue / conférence</dt>
              <dd>{work.venue ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-gray-500">DOI</dt>
              <dd>{work.doi ?? "—"}</dd>
            </div>
            <div>
              <dt className="font-medium text-gray-500">Type de publication</dt>
              <dd>{work.publication_type ? PUBLICATION_TYPE_LABELS[work.publication_type] : "—"}</dd>
            </div>
            <div className="col-span-2">
  <dt className="font-medium text-gray-500">Lien</dt>
  <dd>
    {work.external_url ? (
      <a
        href={work.external_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-600 underline"
      >
        Voir la source
      </a>
    ) : work.file_url ? (
      // Dépôt manuel : pas d'external_url (pas de source web), mais le
      // fichier déposé lui-même est consultable via file_url (Cloudinary).
      <a
        href={work.file_url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-indigo-600 underline"
      >
        Voir le fichier déposé
      </a>
    ) : (
      "—"
    )}
  </dd>
</div>
          </dl>
        </>
      )}

      {allFieldGroups.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-gray-100 pt-3">
          {(mode === "closed" ? readOnlyFieldGroups.length > 0 : allFieldGroups.length > 0) && (
            <p className="text-xs font-medium text-gray-500">Informations complémentaires</p>
          )}

          {mode === "review"
            ? allFieldGroups.map(([fieldName, values]) =>
                MULTI_VALUE_FIELD_NAMES.has(fieldName) ? (
                  <MultiValueFieldGroup key={fieldName} fieldName={fieldName} values={values} onValidate={onValidate} />
                ) : (
                  <GeneratedFieldCard key={values[0].id} field={values[0]} onValidate={onValidate} />
                ),
              )
            : mode === "edit"
              ? allFieldGroups.map(([fieldName, values]) => (
                  <DirectEditFieldGroup key={fieldName} fieldName={fieldName} values={values} onValidate={onValidate} />
                ))
              : readOnlyFieldGroups.map(([fieldName, values]) => (
                  <ReadOnlyFieldGroup key={fieldName} fieldName={fieldName} values={values} />
                ))}
        </div>
      )}

      {/* Cas où l'appel LLM initial a échoué (rate limit Groq typiquement,
          voir research_extraction_service.py) : le travail existe mais n'a
          jamais eu de champs générés (paper_summary, methodology...). Pas de
          retry automatique en I0 — rattrapage manuel uniquement. */}
      {readOnlyFieldGroups.length === 0 && work.abstract && (
        <RegenerateAnalysisButton workId={work.id} onReload={onReload} />
      )}
    </div>
  )
}

interface ReadOnlyFieldGroupProps {
  fieldName: string
  values: FieldValue[]
}

/** Vue par défaut d'un champ généré — affiche la/les valeur(s) actuelle(s)
 * telles quelles (pending ou confirmée, peu importe), sans Modifier/
 * Confirmer/Rejeter. Ces actions n'apparaissent que dans le mode "Consulter
 * les champs à confirmer" (voir le mode "review" dans WorkDetails) — évite
 * que la card soit couverte de boutons avant même que le chercheur ait
 * demandé à valider quoi que ce soit. */
function ReadOnlyFieldGroup({ fieldName, values }: ReadOnlyFieldGroupProps) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-500">{FIELD_NAME_LABELS[fieldName] ?? fieldName}</p>
      {values.map((v) => (
        <p key={v.id} className="text-sm text-gray-700">
          {formatFieldValue(fieldName, v.field_value)}
        </p>
      ))}
    </div>
  )
}

interface DirectEditFieldGroupProps {
  fieldName: string
  values: FieldValue[]
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
}

/** Mode "edit" (bouton "Modifier" toujours visible) — contrairement au mode
 * "review" (GeneratedFieldCard/MultiValueFieldGroup), aucun bouton
 * Confirmer/Rejeter ici : uniquement un champ éditable + un bouton
 * Enregistrer par valeur. Sert à corriger une valeur directement, sans
 * passer par le workflow de validation pending → confirmé/rejeté. Une
 * édition confirme quand même automatiquement côté backend
 * (source=user_added, voir docstring de GeneratedFieldCard.handleSaveEdit)
 * — juste sans exposer ce détail dans l'UI de ce mode. */
function DirectEditFieldGroup({ fieldName, values, onValidate }: DirectEditFieldGroupProps) {
  return (
    <div className="rounded-lg bg-white px-3 py-2 ring-1 ring-gray-200">
      <p className="mb-1.5 text-xs font-medium text-gray-700">{FIELD_NAME_LABELS[fieldName] ?? fieldName}</p>
      <div className="flex flex-col gap-2">
        {values.map((field) => (
          <DirectEditRow key={field.id} field={field} onValidate={onValidate} />
        ))}
      </div>
    </div>
  )
}

interface DirectEditRowProps {
  field: FieldValue
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
}

function DirectEditRow({ field, onValidate }: DirectEditRowProps) {
  const [value, setValue] = useState(field.field_value)
  const [isSaving, setIsSaving] = useState(false)
  // Désactive Enregistrer tant que rien n'a changé — évite un appel PATCH
  // inutile qui ne ferait que reconfirmer la même valeur.
  const isDirty = value !== field.field_value

  async function handleSave() {
    if (!value.trim()) return
    setIsSaving(true)
    try {
      await onValidate(field.id, "edit", value)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex items-start gap-2">
      {field.field_name === "publication_type" ? (
        // Select dédié plutôt qu'un texte libre : la colonne research_works
        // a une contrainte CHECK sur les 5 valeurs autorisées.
        <select
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="flex-1 rounded-lg border border-gray-300 px-2 py-1 text-sm text-gray-700"
        >
          {PUBLICATION_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      ) : (
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={field.field_name === "title" ? 1 : 3}
          className="flex-1 rounded-lg border border-gray-300 px-2 py-1 text-sm"
        />
      )}
      <button
        type="button"
        onClick={handleSave}
        disabled={isSaving || !value.trim() || !isDirty}
        className="shrink-0 self-start rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        {isSaving ? "..." : "Enregistrer"}
      </button>
    </div>
  )
}

interface RegenerateAnalysisButtonProps {
  workId: string
  onReload: () => void
}

function RegenerateAnalysisButton({ workId, onReload }: RegenerateAnalysisButtonProps) {
  const { accessToken } = useAuth()
  const [status, setStatus] = useState<"idle" | "processing" | "done" | "failed">("idle")

  async function handleClick() {
    if (!accessToken) return
    setStatus("processing")
    try {
      await regenerateAnalysis(accessToken, workId)
      setStatus("done")
      // Tâche de fond côté backend, pas de statut par travail (dette
      // technique documentée) — un seul rechargement différé plutôt qu'un
      // polling dédié, pour rester simple : le chercheur peut retenter le
      // bouton "Régénérer" si ça n'a pas suffi.
      window.setTimeout(onReload, 5000)
    } catch {
      setStatus("failed")
    }
  }

  return (
    <div className="border-t border-gray-100 pt-3">
      <p className="mb-1 text-xs text-gray-500">
        Aucun champ généré pour ce travail — l'analyse initiale a probablement échoué.
      </p>
      <button
        type="button"
        onClick={handleClick}
        disabled={status === "processing"}
        className="text-xs font-medium text-indigo-600 disabled:opacity-50"
      >
        {status === "processing" ? "Lancement..." : "Régénérer les champs générés"}
      </button>
      {status === "done" && (
        <p className="mt-1 text-xs text-gray-500">Régénération lancée — actualisation dans quelques secondes.</p>
      )}
      {status === "failed" && <p className="mt-1 text-xs text-red-600">Échec du lancement, réessaie.</p>}
    </div>
  )
}

interface GeneratedFieldCardProps {
  field: FieldValue
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
}

/** Card pour un champ à valeur unique (paper_summary, methodology,
 * key_findings...). Confirmer/Rejeter uniquement tant que pending ; une fois
 * confirmé, plus aucun badge de statut — juste le bouton Modifier reste,
 * pour permettre une correction même après validation. isValidating évite
 * le double-clic qui provoquait des 400 (confirm/reject sur une ligne déjà
 * traitée par la requête précédente). */
function GeneratedFieldCard({ field, onValidate }: GeneratedFieldCardProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [value, setValue] = useState(field.field_value)
  const [isSaving, setIsSaving] = useState(false)
  const [isValidating, setIsValidating] = useState(false)
  const isPending = field.validation_status === "pending_confirmation"

  async function handleSaveEdit() {
    if (!value.trim()) return
    setIsSaving(true)
    try {
      // L'édition confirme automatiquement côté backend (source=user_added
      // → confirmé immédiatement) : pas besoin d'un bouton "Confirmer" séparé après.
      await onValidate(field.id, "edit", value)
      setIsEditing(false)
    } finally {
      setIsSaving(false)
    }
  }

  async function handleValidateClick(action: "confirm" | "reject") {
    setIsValidating(true)
    try {
      await onValidate(field.id, action)
    } finally {
      setIsValidating(false)
    }
  }

  if (isEditing) {
    return (
      <div className="rounded-lg bg-amber-50 px-3 py-2">
        <p className="mb-1 text-xs font-medium text-amber-800">
          {FIELD_NAME_LABELS[field.field_name] ?? field.field_name}
        </p>
        {field.field_name === "publication_type" ? (
          // Select dédié plutôt qu'un texte libre : la colonne research_works
          // a une contrainte CHECK sur les 5 valeurs autorisées, un texte
          // libre pourrait la violer à la matérialisation.
          <select
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm text-gray-700"
          >
            {PUBLICATION_TYPES.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        ) : (
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-2 py-1 text-sm"
          />
        )}
        <div className="mt-2 flex justify-end gap-2">
          <button type="button" onClick={() => setIsEditing(false)} className="text-xs text-gray-500">
            Annuler
          </button>
          <button
            type="button"
            onClick={handleSaveEdit}
            disabled={isSaving || !value.trim()}
            className="rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
          >
            {isSaving ? "Enregistrement..." : "Enregistrer et confirmer"}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-lg px-3 py-2 ${isPending ? "bg-amber-50" : "bg-gray-50"}`}
    >
      <div className="min-w-0">
        <p className={`text-xs font-medium ${isPending ? "text-amber-800" : "text-gray-500"}`}>
          {FIELD_NAME_LABELS[field.field_name] ?? field.field_name}
        </p>
        <p className="text-sm text-gray-700">{formatFieldValue(field.field_name, field.field_value)}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          disabled={isValidating}
          className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-200 hover:bg-indigo-50 disabled:opacity-50"
        >
          Modifier
        </button>
        {isPending && (
          <>
            <button
              type="button"
              onClick={() => handleValidateClick("confirm")}
              disabled={isValidating}
              className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-green-200 hover:bg-green-50 disabled:opacity-50"
            >
              Confirmer
            </button>
            <button
              type="button"
              onClick={() => handleValidateClick("reject")}
              disabled={isValidating}
              className="rounded-lg bg-white px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-red-200 hover:bg-red-50 disabled:opacity-50"
            >
              Rejeter
            </button>
          </>
        )}
      </div>
    </div>
  )
}

interface MultiValueFieldGroupProps {
  fieldName: string
  values: FieldValue[]
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
}

/** Card pour un champ multi-valeur (application_domains...) : une seule card
 * pour le field_name, chaque valeur listée à l'intérieur. Rejeté = filtré en
 * amont, jamais affiché ici. Confirmé = plus de badge, juste Modifier
 * disponible en permanence. */
function MultiValueFieldGroup({ fieldName, values, onValidate }: MultiValueFieldGroupProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [validatingId, setValidatingId] = useState<string | null>(null)

  async function handleValidateClick(fieldId: string, action: "confirm" | "reject") {
    setValidatingId(fieldId)
    try {
      await onValidate(fieldId, action)
    } finally {
      setValidatingId(null)
    }
  }

  return (
    <div className="rounded-lg bg-amber-50 px-3 py-2">
      <p className="mb-1.5 text-xs font-medium text-amber-800">{FIELD_NAME_LABELS[fieldName] ?? fieldName}</p>
      <div className="flex flex-col gap-1.5">
        {values.map((field) =>
          editingId === field.id ? (
            <MultiValueEditRow key={field.id} field={field} onValidate={onValidate} onDone={() => setEditingId(null)} />
          ) : (
            <div key={field.id} className="flex items-center justify-between gap-3">
              <p className="text-sm text-gray-700">{field.field_value}</p>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  onClick={() => setEditingId(field.id)}
                  disabled={validatingId === field.id}
                  className="text-xs font-medium text-indigo-700 disabled:opacity-50"
                >
                  Modifier
                </button>
                {field.validation_status === "pending_confirmation" && (
                  <>
                    <button
                      type="button"
                      onClick={() => handleValidateClick(field.id, "confirm")}
                      disabled={validatingId === field.id}
                      className="text-xs font-medium text-green-700 disabled:opacity-50"
                    >
                      Confirmer
                    </button>
                    <button
                      type="button"
                      onClick={() => handleValidateClick(field.id, "reject")}
                      disabled={validatingId === field.id}
                      className="text-xs font-medium text-red-700 disabled:opacity-50"
                    >
                      Rejeter
                    </button>
                  </>
                )}
              </div>
            </div>
          ),
        )}
      </div>
    </div>
  )
}

interface MultiValueEditRowProps {
  field: FieldValue
  onValidate: (fieldValueId: string, action: ValidateAction, newValue?: string) => void
  onDone: () => void
}

function MultiValueEditRow({ field, onValidate, onDone }: MultiValueEditRowProps) {
  const [value, setValue] = useState(field.field_value)
  const [isSaving, setIsSaving] = useState(false)

  async function handleSave() {
    if (!value.trim()) return
    setIsSaving(true)
    try {
      await onValidate(field.id, "edit", value)
      onDone()
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="flex-1 rounded-lg border border-gray-300 px-2 py-1 text-sm"
      />
      <button type="button" onClick={onDone} className="text-xs text-gray-500">
        Annuler
      </button>
      <button
        type="button"
        onClick={handleSave}
        disabled={isSaving || !value.trim()}
        className="rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white disabled:opacity-50"
      >
        {isSaving ? "..." : "Enregistrer"}
      </button>
    </div>
  )
}