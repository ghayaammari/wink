import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import ComplianceScoreBadge from "../components/compliance/ComplianceScoreBadge"
import { useCopilot } from "../context/CopilotContext"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  getAiActClassification,
  getAiActObligations,
  getAiActProfile,
  getAiActScore,
  runAiActDiagnostic,
  updateAiActObligationStatut,
  updateAiActProfile,
  type AiActDataProfileRead,
  type CategorieRisqueAiAct,
  type ComplianceScoreRead,
  type ObligationStatut,
  type ProjectAiActClassificationRead,
  type ProjectAiActObligationRead,
} from "../api/aiActApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

// Champ tri-état du diagnostic — mêmes 6 champs que AiActDataProfileUpdate
// (backend/entrepreneur/schemas/ai_act_data_profile_schemas.py). Texte des
// questions dupliqué depuis les `Field(description=...)` de ce schéma (source
// de vérité côté backend), même convention que RgpdDiagnosticPage.
type ProfileField =
  | "utilise_ia"
  | "usage_biometrie_ou_identification"
  | "usage_scoring_emploi_credit_ou_education"
  | "usage_infrastructure_ou_securite_critique"
  | "interagit_ou_genere_contenu_pour_utilisateurs"
  | "developpe_modele_ia_usage_general"

// `utilise_ia` est la question "porte" : posée seule en premier, les 5
// suivantes ne sont affichées que si la réponse est `true` (si `false`, le
// backend court-circuite tout calcul — voir ai_act_diagnostic_service.py —
// donc les poser serait trompeur pour l'entrepreneur).
const GATE_QUESTION: { field: ProfileField; texte: string } = {
  field: "utilise_ia",
  texte:
    "Votre projet utilise-t-il un système d'intelligence artificielle dans son fonctionnement (au sens du règlement européen sur l'IA — modèle de machine learning, LLM, système de recommandation automatisé...) ?",
}

const CONDITIONAL_QUESTIONS: { field: ProfileField; texte: string }[] = [
  {
    field: "usage_biometrie_ou_identification",
    texte:
      "Votre système réalise-t-il de l'identification biométrique à distance ou de la catégorisation biométrique de personnes (reconnaissance faciale, analyse d'émotions, catégorisation par caractéristiques physiques) ?",
  },
  {
    field: "usage_scoring_emploi_credit_ou_education",
    texte:
      "Votre système est-il utilisé pour évaluer, sélectionner ou noter des personnes dans un contexte de recrutement/emploi, d'octroi de crédit, ou d'éducation/examens ?",
  },
  {
    field: "usage_infrastructure_ou_securite_critique",
    texte:
      "Votre système est-il utilisé pour gérer ou sécuriser une infrastructure critique (énergie, eau, transport...) ou un dispositif de sécurité ?",
  },
  {
    field: "interagit_ou_genere_contenu_pour_utilisateurs",
    texte:
      "Votre système interagit-il directement avec les utilisateurs (chatbot, assistant conversationnel) ou génère-t-il du contenu (texte, image, audio, vidéo) qui leur est présenté ?",
  },
  {
    field: "developpe_modele_ia_usage_general",
    texte:
      "Développez-vous vous-même un modèle d'IA à usage général/de fondation (par opposition à l'utilisation d'une API tierce existante comme OpenAI, Groq...) ?",
  },
]

// Libellés d'affichage des 5 catégories de risque AI Act (voir
// CategorieRisqueAiAct côté backend, reprise de la taxonomie du règlement).
const CATEGORIE_LABELS: Record<CategorieRisqueAiAct, string> = {
  interdit: "Pratique interdite",
  haut_risque: "Haut risque",
  risque_limite: "Risque limité",
  gouvernance_gpai: "Gouvernance GPAI",
  minimal: "Risque minimal",
}

const CATEGORIE_STYLES: Record<CategorieRisqueAiAct, string> = {
  interdit: "bg-red-100 text-red-800 border-red-200",
  haut_risque: "bg-orange-100 text-orange-800 border-orange-200",
  risque_limite: "bg-amber-100 text-amber-800 border-amber-200",
  gouvernance_gpai: "bg-blue-100 text-blue-800 border-blue-200",
  minimal: "bg-green-100 text-green-800 border-green-200",
}

/**
 * Détail du service 3.3.12 (diagnostic AI Act) — carte ouverte depuis
 * CompliancePlanPage. Trois blocs : le questionnaire tri-état (ai_act_data_profile,
 * une question = un PATCH immédiat sur ce seul champ), la classification de
 * risque (project_ai_act_classification, en lecture seule, mise à jour
 * uniquement via le diagnostic), et la liste des obligations
 * (project_ai_act_obligations) — recalculées uniquement via le bouton
 * "Recalculer mon diagnostic", jamais automatiquement après une réponse
 * (même raisonnement que RgpdDiagnosticPage).
 */
export default function AiActDiagnosticPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const arriveDepuisCopilot = searchParams.get("from") === "copilot"
  const { addAssistantMessage } = useCopilot()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [profile, setProfile] = useState<AiActDataProfileRead | null>(null)
  const [classification, setClassification] = useState<ProjectAiActClassificationRead | null>(null)
  const [obligations, setObligations] = useState<ProjectAiActObligationRead[]>([])
  const [score, setScore] = useState<ComplianceScoreRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savingField, setSavingField] = useState<ProfileField | null>(null)
  const [isRecalculating, setIsRecalculating] = useState(false)
  const [recalcError, setRecalcError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      const [currentProfile, currentClassification, currentObligations, currentScore] = await Promise.all([
        getAiActProfile(accessToken, project.id),
        getAiActClassification(accessToken, project.id),
        getAiActObligations(accessToken, project.id),
        getAiActScore(accessToken, project.id),
      ])
      setProfile(currentProfile)
      setClassification(currentClassification)
      setObligations(currentObligations)
      setScore(currentScore)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger le diagnostic AI Act.")
      setState("error")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de token
  }, [accessToken])

  async function handleAnswer(field: ProfileField, value: boolean | null) {
    if (!accessToken || !projectId) return
    setSavingField(field)
    try {
      const updated = await updateAiActProfile(accessToken, projectId, { [field]: value })
      setProfile(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la réponse.")
    } finally {
      setSavingField(null)
    }
  }

  async function handleToggleObligation(obligation: ProjectAiActObligationRead) {
    if (!accessToken || !projectId) return
    const nextStatut: ObligationStatut = obligation.statut === "fait" ? "a_faire" : "fait"
    const updated = await updateAiActObligationStatut(accessToken, projectId, obligation.id, nextStatut)
    setObligations((current) => current.map((o) => (o.id === updated.id ? updated : o)))
    setScore(await getAiActScore(accessToken, projectId))
  }

  async function handleRecalculer() {
    if (!accessToken || !projectId) return
    setIsRecalculating(true)
    setRecalcError(null)
    try {
      const result = await runAiActDiagnostic(accessToken, projectId)
      setClassification(result.classification)
      setObligations(result.obligations)
      setScore(await getAiActScore(accessToken, projectId))
    } catch (err) {
      // 502 attendu si Groq échoue après ses retries (voir AiActAgentError ->
      // ai_act_router._handle_ai_act_error) : message générique, pas de
      // détail technique brut affiché à l'entrepreneur.
      setRecalcError(
        err instanceof ApiError
          ? "Le calcul du diagnostic a échoué, réessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setIsRecalculating(false)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
  }
  if (!profile || !classification) return null

  function handleTerminer() {
    // Ne telecharge plus rien ici (voir CopilotContext.tsx) : le rapport
    // n'est genere/telecharge qu'au clic sur le bouton correspondant dans
    // le chat du copilot, jamais automatiquement au clic sur "Terminer".
    const scoreTexte = score?.score !== undefined && score.score !== null ? `${score.score}%` : "non disponible (aucune obligation évaluée)"
    addAssistantMessage(`Diagnostic AI Act termine. Score de conformite final : ${scoreTexte}.`, "ai-act")
    navigate("/entrepreneur/copilot")
  }

  // Les questions conditionnelles n'ont de sens que si le projet utilise
  // effectivement de l'IA — si `utilise_ia` est `false`, le backend court-
  // circuite le diagnostic (catégorie "minimal" directe), donc les masquer
  // évite de faire répondre à des questions sans effet.
  const showConditionalQuestions = profile.utilise_ia !== false

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold text-gray-900">Diagnostic AI Act</h1>
          <p className="text-sm text-gray-500">
            Réponds aux questions ci-dessous, puis recalcule ton diagnostic pour obtenir ta catégorie de risque et
            tes obligations au titre du règlement européen sur l'intelligence artificielle.
          </p>
        </div>
        {arriveDepuisCopilot && (
          <button
            type="button"
            onClick={handleTerminer}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100"
          >
            Terminer et revenir au copilot
          </button>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <QuestionCard
          field={GATE_QUESTION.field}
          texte={GATE_QUESTION.texte}
          value={profile[GATE_QUESTION.field]}
          isSaving={savingField === GATE_QUESTION.field}
          onAnswer={handleAnswer}
        />

        {showConditionalQuestions &&
          CONDITIONAL_QUESTIONS.map(({ field, texte }) => (
            <QuestionCard
              key={field}
              field={field}
              texte={texte}
              value={profile[field]}
              isSaving={savingField === field}
              onAnswer={handleAnswer}
            />
          ))}
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-gray-900">Ton diagnostic</h2>
          <button
            type="button"
            onClick={handleRecalculer}
            disabled={isRecalculating}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isRecalculating ? "Calcul en cours..." : "Recalculer mon diagnostic"}
          </button>
        </div>

        {score && <ComplianceScoreBadge score={score.score} totalObligations={score.total_obligations} />}

        {recalcError && <p className="text-sm text-red-600">{recalcError}</p>}

        {classification.categorie_risque === null ? (
          <p className="text-sm text-gray-500">
            Aucun diagnostic calculé pour l'instant — clique sur "Recalculer mon diagnostic".
          </p>
        ) : (
          <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-gray-900">Rapport d'étude de risque</h3>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${CATEGORIE_STYLES[classification.categorie_risque]}`}
              >
                {CATEGORIE_LABELS[classification.categorie_risque]}
              </span>
            </div>
            {classification.justification && (
              // Le rapport est structuré en plusieurs paragraphes par l'agent
              // (contexte / critères déclencheurs / raisonnement / implications,
              // voir prompts.yaml::regulatory_agent_ai_act.diagnostic) séparés
              // par un saut de ligne vide — on les affiche comme des <p>
              // distincts plutôt qu'un seul bloc de texte pour rester lisible.
              <div className="flex flex-col gap-3">
                {classification.justification
                  .split(/\n\s*\n/)
                  .map((paragraphe) => paragraphe.trim())
                  .filter(Boolean)
                  .map((paragraphe, index) => (
                    <p key={index} className="text-sm text-gray-700">
                      {paragraphe}
                    </p>
                  ))}
              </div>
            )}
          </div>
        )}

        {obligations.length > 0 && (
          <>
            <h3 className="text-sm font-semibold text-gray-900">Obligations à respecter</h3>
            <ul className="flex flex-col gap-3">
            {obligations.map((obligation) => (
              <li key={obligation.id} className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4">
                <input
                  type="checkbox"
                  checked={obligation.statut === "fait"}
                  onChange={() => handleToggleObligation(obligation)}
                  className="mt-1 h-4 w-4 shrink-0 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <div className="flex flex-col gap-1">
                  <span
                    className={`text-sm font-medium ${
                      obligation.statut === "fait" ? "text-gray-400 line-through" : "text-gray-900"
                    }`}
                  >
                    {obligation.nom}
                  </span>
                  <span className="text-xs text-gray-500">{obligation.description}</span>
                </div>
              </li>
            ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Une question tri-état (Oui / Non / Pas encore répondu) — factorisée car
 * utilisée à l'identique pour la question porte et les 5 conditionnelles
 * (voir AiActDiagnosticPage ci-dessus).
 */
function QuestionCard({
  field,
  texte,
  value,
  isSaving,
  onAnswer,
}: {
  field: ProfileField
  texte: string
  value: boolean | null
  isSaving: boolean
  onAnswer: (field: ProfileField, value: boolean | null) => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-sm text-gray-800">{texte}</p>
      <div className="flex gap-2">
        {(
          [
            { label: "Oui", value: true as boolean | null },
            { label: "Non", value: false as boolean | null },
            { label: "Pas encore répondu", value: null as boolean | null },
          ] satisfies { label: string; value: boolean | null }[]
        ).map((option) => {
          const isActive = value === option.value
          return (
            <button
              key={option.label}
              type="button"
              disabled={isSaving}
              onClick={() => onAnswer(field, option.value)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                isActive ? "bg-indigo-600 text-white" : "border border-gray-200 text-gray-600 hover:border-gray-300"
              }`}
            >
              {option.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
