import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import ComplianceScoreBadge from "../components/compliance/ComplianceScoreBadge"
import { useCopilot } from "../context/CopilotContext"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  getRgpdObligations,
  getRgpdProfile,
  getRgpdScore,
  runRgpdDiagnostic,
  updateRgpdObligationStatut,
  updateRgpdProfile,
  type ComplianceDataProfileRead,
  type ComplianceScoreRead,
  type ObligationStatut,
  type ProjectRgpdObligationRead,
} from "../api/rgpdApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

// Champ tri-état du diagnostic — même 5 champs que ComplianceDataProfileUpdate
// (backend/entrepreneur/schemas/compliance_data_profile_schemas.py). Le texte
// des questions est dupliqué depuis les `Field(description=...)` de ce schéma
// (source de vérité côté backend) : c'est le seul endroit qui les affiche à
// l'utilisateur, donc une copie ici plutôt qu'un mécanisme pour les récupérer
// dynamiquement — si le texte change côté backend, mettre à jour cette liste
// aussi (5 lignes, pas de quoi construire une API dédiée juste pour ça).
type ProfileField =
  | "collecte_donnees_sensibles"
  | "collecte_donnees_mineurs"
  | "profilage"
  | "partage_avec_tiers"
  | "transfert_hors_ue"

const QUESTIONS: { field: ProfileField; texte: string }[] = [
  {
    field: "collecte_donnees_sensibles",
    texte:
      "Votre projet collecte-t-il des données personnelles sensibles au sens du RGPD (santé, origine raciale ou ethnique, opinions politiques ou religieuses, appartenance syndicale, vie sexuelle ou orientation sexuelle, données biométriques ou génétiques) ?",
  },
  {
    field: "collecte_donnees_mineurs",
    texte:
      "Votre service est-il proposé directement à des mineurs de moins de 15 ans (ex : application ou plateforme accessible à des enfants ou adolescents) ?",
  },
  {
    field: "profilage",
    texte:
      "Votre projet réalise-t-il un profilage automatisé de vos utilisateurs (scoring, recommandation personnalisée, décision automatisée les concernant) ?",
  },
  {
    field: "partage_avec_tiers",
    texte:
      "Faites-vous appel à des prestataires qui traitent des données pour votre compte (hébergeur, outil d'emailing, paiement, analytics...), ou partagez-vous des données personnelles avec des partenaires externes ?",
  },
  {
    field: "transfert_hors_ue",
    texte:
      "Une partie de ces données est-elle hébergée ou traitée en dehors de l'Union européenne (ex : prestataire américain, hébergement cloud hors UE) ?",
  },
]

function ICON_QUESTIONNAIRE({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 4.5h6a1.5 1.5 0 011.5 1.5v1H7.5v-1A1.5 1.5 0 019 4.5z" />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 7h12a1 1 0 011 1v10.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 015 18.5V8a1 1 0 011-1z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 11.5h6M9 14.5h6M9 17.5h3.5" />
    </svg>
  )
}

function ICON_CHEVRON_DOWN({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
    </svg>
  )
}

function ICON_CHECK({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  )
}

function ICON_SHIELD_HEADER({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 12l1.8 1.8L14.5 10" />
    </svg>
  )
}

/**
 * Détail du service 3.3.1 (diagnostic RGPD) — carte ouverte depuis
 * CompliancePlanPage. Deux blocs : le questionnaire tri-état
 * (compliance_data_profile, une question = un PATCH immédiat sur ce seul
 * champ) et la liste des obligations (project_rgpd_obligations), recalculée
 * uniquement via le bouton "Recalculer mes obligations" — jamais
 * automatiquement après une réponse, voir docstring de rgpd_router.py.
 *
 * Questionnaire replié par défaut (accordéon) : ajouté le 26/09/2026 pour ne
 * pas noyer l'entrepreneur sous 5 questions dès l'arrivée sur la page —
 * conserve exactement la même logique de sauvegarde (un clic = un PATCH),
 * seul l'affichage change (pas de nouvel état serveur, juste `isQuestionnaireOpen`
 * en local).
 */
export default function RgpdDiagnosticPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // Present uniquement si on arrive depuis un lien du copilot (voir
  // CopilotSidebar.tsx, handleRedirection) -- seul cas ou le bouton
  // "Terminer" a un sens : rendre la main au copilot avec le rapport
  // genere, pas pertinent pour une visite directe de cette page.
  const arriveDepuisCopilot = searchParams.get("from") === "copilot"
  const { addAssistantMessage } = useCopilot()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [profile, setProfile] = useState<ComplianceDataProfileRead | null>(null)
  const [obligations, setObligations] = useState<ProjectRgpdObligationRead[]>([])
  const [score, setScore] = useState<ComplianceScoreRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [savingField, setSavingField] = useState<ProfileField | null>(null)
  const [isRecalculating, setIsRecalculating] = useState(false)
  const [recalcError, setRecalcError] = useState<string | null>(null)
  const [isQuestionnaireOpen, setIsQuestionnaireOpen] = useState(false)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      const [currentProfile, currentObligations, currentScore] = await Promise.all([
        getRgpdProfile(accessToken, project.id),
        getRgpdObligations(accessToken, project.id),
        getRgpdScore(accessToken, project.id),
      ])
      setProfile(currentProfile)
      setObligations(currentObligations)
      setScore(currentScore)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger le diagnostic RGPD.")
      setState("error")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de token
  }, [accessToken])

  async function handleAnswer(field: ProfileField, value: boolean | null) {
    if (!accessToken || !projectId) return
    setSavingField(field)
    try {
      const updated = await updateRgpdProfile(accessToken, projectId, { [field]: value })
      setProfile(updated)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la réponse.")
    } finally {
      setSavingField(null)
    }
  }

  async function handleToggleObligation(obligation: ProjectRgpdObligationRead) {
    if (!accessToken || !projectId) return
    const nextStatut: ObligationStatut = obligation.statut === "fait" ? "a_faire" : "fait"
    const updated = await updateRgpdObligationStatut(accessToken, projectId, obligation.id, nextStatut)
    setObligations((current) => current.map((o) => (o.id === updated.id ? updated : o)))
    // Le score depend du statut des obligations : on le recalcule apres
    // chaque bascule, sinon il resterait fige a l'ancienne valeur.
    setScore(await getRgpdScore(accessToken, projectId))
  }

  async function handleRecalculer() {
    if (!accessToken || !projectId) return
    setIsRecalculating(true)
    setRecalcError(null)
    try {
      const updated = await runRgpdDiagnostic(accessToken, projectId)
      setObligations(updated)
      setScore(await getRgpdScore(accessToken, projectId))
    } catch (err) {
      // 502 attendu si Groq échoue après ses retries (voir RegulatoryAgentError
      // -> rgpd_router._handle_rgpd_error) : message générique, pas de detail
      // technique brut affiché à l'entrepreneur.
      setRecalcError(
        err instanceof ApiError
          ? "Le calcul des obligations a échoué, réessaie dans quelques instants."
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
  if (!profile) return null

  function handleTerminer() {
    // Ne telecharge plus rien ici (voir CopilotContext.tsx) : le rapport
    // n'est genere/telecharge qu'au clic sur le bouton correspondant dans
    // le chat du copilot, jamais automatiquement au clic sur "Terminer".
    const scoreTexte = score?.score !== undefined && score.score !== null ? `${score.score}%` : "non disponible (aucune obligation évaluée)"
    addAssistantMessage(`Diagnostic RGPD termine. Score de conformite final : ${scoreTexte}.`, "rgpd")
    navigate("/entrepreneur/copilot")
  }

  // Regroupement demande le 17/09/2026 : les obligations liees a une AIPD
  // sont affichees a part, en bas, pour que l'entrepreneur comprenne que ce
  // sont des obligations d'un type different (declenchees par un besoin
  // d'analyse d'impact) plutot qu'une liste plate sans distinction.
  const obligationsStandard = obligations.filter((o) => !o.lie_a_aipd)
  const obligationsAipd = obligations.filter((o) => o.lie_a_aipd)
  const nombreReponses = QUESTIONS.filter(({ field }) => profile[field] !== null).length

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
            <ICON_SHIELD_HEADER className="h-4 w-4" />
          </div>
          <div className="flex flex-col gap-0.5">
            <h1 className="text-xl font-semibold text-gray-900">Diagnostic RGPD</h1>
            <p className="text-sm text-gray-500">
              Réponds aux questions ci-dessous, puis recalcule tes obligations. Certaines obligations de base
              s'appliquent même si tu ne réponds à aucune question — voir la liste plus bas.
            </p>
          </div>
        </div>
        {arriveDepuisCopilot && (
          <button
            type="button"
            onClick={handleTerminer}
            className="rounded-lg border border-wink-200 bg-wink-50 px-3 py-2 text-sm font-medium text-wink-700 transition hover:bg-wink-100"
          >
            Terminer et revenir au copilot
          </button>
        )}
      </div>

      <div className="flex flex-col">
        <button
          type="button"
          onClick={() => setIsQuestionnaireOpen((open) => !open)}
          aria-expanded={isQuestionnaireOpen}
          className="flex w-full items-center justify-between rounded-xl border border-wink-200 bg-wink-50 px-4 py-3 text-left transition hover:bg-wink-100"
        >
          <span className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-wink-600 text-white">
              <ICON_QUESTIONNAIRE className="h-4 w-4" />
            </span>
            <span className="flex flex-col">
              <span className="text-sm font-semibold text-wink-800">Questionnaire</span>
              <span className="text-xs text-wink-600">
                {nombreReponses}/{QUESTIONS.length} question{QUESTIONS.length > 1 ? "s" : ""} répondue
                {nombreReponses > 1 ? "s" : ""}
              </span>
            </span>
          </span>
          <ICON_CHEVRON_DOWN
            className={`h-5 w-5 shrink-0 text-wink-600 transition-transform duration-200 ${
              isQuestionnaireOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        <div
          className={`grid transition-all duration-300 ease-in-out ${
            isQuestionnaireOpen ? "mt-3 grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
          }`}
        >
          <div className="overflow-hidden">
            <div className="flex flex-col gap-3">
              {QUESTIONS.map(({ field, texte }, index) => (
                <div
                  key={field}
                  className="flex flex-col gap-3 rounded-xl border border-gray-200 border-l-4 border-l-wink-300 bg-white p-4 transition hover:border-wink-200 hover:border-l-wink-400"
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-wink-50 text-xs font-semibold text-wink-700">
                      {index + 1}
                    </span>
                    <p className="min-w-0 flex-1 text-sm text-gray-800">{texte}</p>
                  </div>
                  <div className="flex flex-wrap gap-2 pl-9">
                    {(
                      [
                        { label: "Oui", value: true as boolean | null },
                        { label: "Non", value: false as boolean | null },
                        { label: "Pas encore répondu", value: null as boolean | null },
                      ] satisfies { label: string; value: boolean | null }[]
                    ).map((option) => {
                      const isActive = profile[field] === option.value
                      return (
                        <button
                          key={option.label}
                          type="button"
                          disabled={savingField === field}
                          onClick={() => handleAnswer(field, option.value)}
                          className={`rounded-full px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                            isActive
                              ? "bg-wink-600 text-white shadow-sm"
                              : "border border-gray-200 text-gray-600 hover:border-wink-300 hover:text-wink-700"
                          }`}
                        >
                          {option.label}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
            <span className="h-2 w-2 rounded-full bg-wink-500" />
            Tes obligations
          </h2>
          <button
            type="button"
            onClick={handleRecalculer}
            disabled={isRecalculating}
            className="rounded-lg bg-wink-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-wink-700 disabled:opacity-50"
          >
            {isRecalculating ? "Calcul en cours..." : "Recalculer mes obligations"}
          </button>
        </div>

        {score && <ComplianceScoreBadge score={score.score} totalObligations={score.total_obligations} />}

        {recalcError && <p className="text-sm text-red-600">{recalcError}</p>}

        {obligations.length === 0 ? (
          <p className="text-sm text-gray-500">
            Aucune obligation calculée pour l'instant — clique sur "Recalculer mes obligations".
          </p>
        ) : (
          <>
            <ul className="flex flex-col gap-3">
              {obligationsStandard.map((obligation) => (
                <ObligationItem key={obligation.id} obligation={obligation} onToggle={handleToggleObligation} />
              ))}
            </ul>

            {obligationsAipd.length > 0 && (
              <ul className="flex flex-col gap-3">
                {obligationsAipd.map((obligation) => (
                  <AipdObligationItem key={obligation.id} obligation={obligation} onToggle={handleToggleObligation} />
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/**
 * Une ligne d'obligation (checkbox + nom + description) — factorisé pour
 * être utilisé identiquement dans la liste standard et le bloc AIPD, sans
 * dupliquer le JSX (voir RgpdDiagnosticPage ci-dessus).
 *
 * Coché = carte + texte en vert, plus de barré (line-through) : changé le
 * 26/09/2026, le barré donnait une impression de "supprimé" plutôt que
 * "fait". La checkbox native est remplacée par un bouton rond custom pour
 * pouvoir styler précisément l'état coché (cercle plein + coche), impossible
 * avec l'apparence par défaut d'un <input type="checkbox">.
 */
function ObligationItem({
  obligation,
  onToggle,
}: {
  obligation: ProjectRgpdObligationRead
  onToggle: (obligation: ProjectRgpdObligationRead) => void
}) {
  const isFait = obligation.statut === "fait"
  return (
    <li
      className={`flex items-start gap-3 rounded-xl border border-l-4 p-4 transition ${
        isFait
          ? "border-wink-200 border-l-wink-500 bg-wink-50"
          : "border-gray-200 border-l-gray-200 bg-white hover:border-l-wink-300"
      }`}
    >
      <button
        type="button"
        role="checkbox"
        aria-checked={isFait}
        onClick={() => onToggle(obligation)}
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
          isFait
            ? "border-wink-600 bg-wink-600 text-white"
            : "border-gray-300 bg-white text-transparent hover:border-wink-400"
        }`}
      >
        <ICON_CHECK className="h-3 w-3" />
      </button>
      <div className="flex flex-col gap-1">
        <span className={`text-sm font-medium transition ${isFait ? "text-wink-700" : "text-gray-900"}`}>
          {obligation.nom}
        </span>
        <span className={`text-xs transition ${isFait ? "text-wink-600" : "text-gray-500"}`}>
          {obligation.description}
        </span>
      </div>
    </li>
  )
}

/**
 * Card distincte pour une obligation qui EST (ou decoule d') un besoin
 * d'AIPD (lie_a_aipd=true) - mise en avant (fond ambre, badge) plutot qu'une
 * simple checkbox parmi les autres, avec un bouton vers le futur generateur
 * d'AIPD (service 3.3.4, pas encore construit - voir aipd_analysis_service.py
 * : le squelette existe cote backend, mais aucune route ni generation reelle
 * pour l'instant, donc le bouton est desactive avec une indication claire).
 *
 * Pas de sous-liste imbriquee ici (contrairement a une premiere version
 * envisagee) : aujourd'hui une seule obligation porte lie_a_aipd=true (le
 * besoin d'AIPD lui-meme), il n'existe pas encore d'obligations "enfants"
 * generees par un vrai service 3.3.4 - inventer cette hierarchie
 * maintenant ajouterait de la structure pour une donnee qui n'existe pas
 * encore (voir discussion du 18/09/2026, meme principe que la decision de
 * ne pas afficher de cards desactivees "a venir" sur CompliancePlanPage).
 *
 * Même changement que ObligationItem le 26/09/2026 (plus de line-through,
 * bouton rond custom) mais palette ambre conservée : cette carte reste
 * volontairement distincte visuellement des obligations standard.
 */
function AipdObligationItem({
  obligation,
  onToggle,
}: {
  obligation: ProjectRgpdObligationRead
  onToggle: (obligation: ProjectRgpdObligationRead) => void
}) {
  const isFait = obligation.statut === "fait"
  return (
    <li className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          aria-checked={isFait}
          onClick={() => onToggle(obligation)}
          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
            isFait
              ? "border-amber-600 bg-amber-600 text-white"
              : "border-amber-300 bg-white text-transparent hover:border-amber-400"
          }`}
        >
          <ICON_CHECK className="h-3 w-3" />
        </button>
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-sm font-medium ${isFait ? "text-amber-700" : "text-amber-900"}`}>
              {obligation.nom}
            </span>
            <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-900">
              AIPD
            </span>
          </div>
          <span className="text-xs text-amber-800">{obligation.description}</span>
        </div>
      </div>
      <Link
        to="/entrepreneur/conformite/aipd"
        className="self-start rounded-md border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-700 transition hover:bg-amber-100"
      >
        Faire mon AIPD
      </Link>
    </li>
  )
}
