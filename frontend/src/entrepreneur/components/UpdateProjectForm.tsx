import { useState, type FormEvent } from "react"
import { ApiError } from "../../shared/api/authApi"
import { updateProject, type ProjectRead, type ProjectUpdate } from "../api/projectApi"
import { IMMEDIATE_OBJECTIVES } from "../utils/projectImmediateObjectives"
import { PROJECT_TYPE_OPTIONS, isStageValidFor, stageOptionsFor } from "../utils/projectStageOptions"

interface UpdateProjectFormProps {
  project: ProjectRead
  accessToken: string
  onSaved: () => void
  onCancel: () => void
}

type IntentionOption = "oui" | "non" | "indecis"

function toIntentionOption(value: boolean | null): IntentionOption {
  if (value === null) return "indecis"
  return value ? "oui" : "non"
}

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

const inputClass = "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
const labelClass = "text-xs font-medium text-gray-700"

/**
 * Formulaire du popup "Mettre à jour" (Informations générales, table `projects`).
 *
 * `project_type`/`stage` sont inclus ici (dropdowns), en plus de leur mécanisme
 * de résolution de conflit (`FieldConflictReview` dans ProjectGeneralInfoPage.tsx,
 * pour les désaccords détectés depuis un document) — les 2 chemins écrivent sur
 * les mêmes colonnes via le même endpoint validé (`PATCH /projects/{id}`, enums
 * Pydantic stricts côté backend), donc pas de risque d'incohérence entre eux.
 * La liste de `stage` se filtre en direct selon `project_type` sélectionné (voir
 * `projectStageOptions.ts`, seule source de vérité partagée avec
 * FieldConflictReview) ; si l'utilisateur change `project_type` sans ajuster un
 * `stage` devenu incompatible, la soumission est bloquée avec une erreur inline
 * sur le champ `stage` plutôt que corrigée silencieusement à sa place.
 *
 * Limitation connue et assumée : si un champ modifié ici a par ailleurs une
 * candidate extraite en attente (badge visible), cette candidate n'est pas
 * touchée par ce formulaire — elle reste `en_attente` et pourra plus tard sembler
 * proposer d'écraser la valeur qu'on vient de saisir manuellement. Pas résolu
 * automatiquement pour l'instant (nécessiterait de lier ce PATCH à la résolution
 * des candidates concernées).
 */
export default function UpdateProjectForm({ project, accessToken, onSaved, onCancel }: UpdateProjectFormProps) {
  const [projectType, setProjectType] = useState(project.project_type)
  const [stage, setStage] = useState<string>(project.stage)
  const [stageError, setStageError] = useState<string | null>(null)
  const [description, setDescription] = useState(project.description ?? "")
  const [sector, setSector] = useState(project.sector ?? "")
  const [subsectors, setSubsectors] = useState(project.subsectors.join(", "))
  const [customerSegments, setCustomerSegments] = useState(project.customer_segments.join(", "))
  const [targetUsers, setTargetUsers] = useState(project.target_users.join(", "))
  const [nombreCofondateurs, setNombreCofondateurs] = useState(project.nombre_cofondateurs?.toString() ?? "")
  const [intention, setIntention] = useState<IntentionOption>(toIntentionOption(project.intention_levee_fonds))
  const [technologies, setTechnologies] = useState(project.technologies.join(", "))
  const [valueProposition, setValueProposition] = useState(project.value_proposition ?? "")
  const [localisation, setLocalisation] = useState(project.localisation ?? "")
  const [objectifsImmediats, setObjectifsImmediats] = useState<string[]>(
    project.objectifs_immediats,
  )

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleObjectif(code: string) {
    setObjectifsImmediats((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    )
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setStageError(null)

    if (!isStageValidFor(projectType, stage)) {
      const validLabels = stageOptionsFor(projectType)
        .map((o) => o.label)
        .join(", ")
      setStageError(
        `Ce stade n'est pas compatible avec "${
          PROJECT_TYPE_OPTIONS.find((o) => o.value === projectType)?.label
        }". Choisis parmi : ${validLabels}.`,
      )
      return
    }

    if (nombreCofondateurs.trim() !== "" && Number(nombreCofondateurs) < 0) {
      setError("Le nombre de cofondateurs ne peut pas être négatif.")
      return
    }

    const payload: ProjectUpdate = {
      project_type: projectType,
      stage: stage as ProjectRead["stage"],
      // description : le backend refuse une chaîne vide (min_length=1) — on ne
      // touche pas au champ plutôt que d'envoyer "" et provoquer une erreur 422.
      ...(description.trim() !== "" ? { description: description.trim() } : {}),
      sector: sector.trim(),
      subsectors: parseList(subsectors),
      customer_segments: parseList(customerSegments),
      target_users: parseList(targetUsers),
      nombre_cofondateurs: nombreCofondateurs.trim() === "" ? undefined : Number(nombreCofondateurs),
      intention_levee_fonds: intention === "indecis" ? null : intention === "oui",
      technologies: parseList(technologies),
      value_proposition: valueProposition,
      localisation: localisation.trim(),
      // Liste complète (pas un diff) : une liste vide efface les objectifs posés
      // précédemment — même sémantique que l'écran 6 de l'onboarding.
      // (réalisé par OPENCODE)
      objectifs_immediats: objectifsImmediats,
    }

    setIsSubmitting(true)
    try {
      await updateProject(accessToken, project.id, payload)
      onSaved()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-project-type">
            Startup
          </label>
          <select
            id="update-project-type"
            value={projectType}
            onChange={(e) => {
              const nextType = e.target.value as ProjectRead["project_type"]
              setProjectType(nextType)
              setStageError(null)
            }}
            className={inputClass}
          >
            {PROJECT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-stage">
            Stade financier
          </label>
          <select
            id="update-stage"
            // Si le stade en mémoire n'est plus valide pour le type sélectionné, on
            // retombe sur l'option vide ci-dessous plutôt que de laisser le navigateur
            // afficher silencieusement le 1er choix réel de la liste comme "sélectionné"
            // (c'était le bug : cliquer sur ce choix ne déclenchait alors aucun
            // changement, puisque le navigateur le considérait déjà actif).
            value={isStageValidFor(projectType, stage) ? stage : ""}
            onChange={(e) => {
              setStage(e.target.value)
              setStageError(null)
            }}
            className={`${inputClass} ${stageError ? "border-red-500 focus:border-red-500" : ""}`}
          >
            <option value="" disabled>
              — Choisis un stade —
            </option>
            {/* La liste se filtre selon "Startup" ci-dessus (voir stageOptionsFor) —
                si le stade actuel n'est plus dans la liste après un changement de
                type, on ne le force pas silencieusement : la soumission bloque avec
                l'erreur ci-dessous tant que l'utilisateur n'a pas choisi lui-même
                un stade valide. */}
            {stageOptionsFor(projectType).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {stageError && <p className="text-xs text-red-600">{stageError}</p>}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-description">
          Description
        </label>
        <textarea
          id="update-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className={inputClass}
        />
        <p className="text-xs text-gray-400">Ne peut pas être vidé depuis ce formulaire.</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-sector">
          Secteur
        </label>
        <input
          id="update-sector"
          type="text"
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-subsectors">
          Sous-secteurs <span className="font-normal text-gray-400">(séparés par des virgules)</span>
        </label>
        <input
          id="update-subsectors"
          type="text"
          value={subsectors}
          onChange={(e) => setSubsectors(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-customer-segments">
          Segments clients <span className="font-normal text-gray-400">(séparés par des virgules)</span>
        </label>
        <input
          id="update-customer-segments"
          type="text"
          value={customerSegments}
          onChange={(e) => setCustomerSegments(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-target-users">
          Utilisateurs cibles <span className="font-normal text-gray-400">(séparés par des virgules)</span>
        </label>
        <input
          id="update-target-users"
          type="text"
          value={targetUsers}
          onChange={(e) => setTargetUsers(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-cofondateurs">
            Cofondateurs
          </label>
          <input
            id="update-cofondateurs"
            type="number"
            min={0}
            value={nombreCofondateurs}
            onChange={(e) => setNombreCofondateurs(e.target.value)}
            className={inputClass}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label className={labelClass} htmlFor="update-intention">
            Intention de levée de fonds
          </label>
          <select
            id="update-intention"
            value={intention}
            onChange={(e) => setIntention(e.target.value as IntentionOption)}
            className={inputClass}
          >
            <option value="indecis">Pas encore décidé</option>
            <option value="oui">Oui</option>
            <option value="non">Non</option>
          </select>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-technologies">
          Technologies <span className="font-normal text-gray-400">(séparées par des virgules)</span>
        </label>
        <input
          id="update-technologies"
          type="text"
          value={technologies}
          onChange={(e) => setTechnologies(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-value-proposition">
          Proposition de valeur
        </label>
        <textarea
          id="update-value-proposition"
          value={valueProposition}
          onChange={(e) => setValueProposition(e.target.value)}
          rows={2}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className={labelClass} htmlFor="update-localisation">
          Localisation
        </label>
        <input
          id="update-localisation"
          type="text"
          value={localisation}
          onChange={(e) => setLocalisation(e.target.value)}
          className={inputClass}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <p className={labelClass}>Objectifs immédiats</p>
        <div className="flex flex-col gap-2">
          {IMMEDIATE_OBJECTIVES.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm transition hover:border-gray-400"
            >
              <input
                type="checkbox"
                checked={objectifsImmediats.includes(option.value)}
                onChange={() => toggleObjectif(option.value)}
                className="h-4 w-4"
              />
              {option.label}
            </label>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="mt-2 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400 disabled:opacity-50"
        >
          Annuler
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Enregistrer"}
        </button>
      </div>
    </form>
  )
}
