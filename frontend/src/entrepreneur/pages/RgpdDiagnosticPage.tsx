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

/**
 * Détail du service 3.3.1 (diagnostic RGPD) — carte ouverte depuis
 * CompliancePlanPage. Deux blocs : le questionnaire tri-état
 * (compliance_data_profile, une question = un PATCH immédiat sur ce seul
 * champ) et la liste des obligations (project_rgpd_obligations), recalculée
 * uniquement via le bouton "Recalculer mes obligations" — jamais
 * automatiquement après une réponse, voir docstring de rgpd_router.py.
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

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold text-gray-900">Diagnostic RGPD</h1>
          <p className="text-sm text-gray-500">
            Réponds aux questions ci-dessous, puis recalcule tes obligations. Certaines obligations de base
            s'appliquent même si tu ne réponds à aucune question — voir la liste plus bas.
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
        {QUESTIONS.map(({ field, texte }) => (
          <div key={field} className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-sm text-gray-800">{texte}</p>
            <div className="flex gap-2">
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
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${
                      isActive
                        ? "bg-indigo-600 text-white"
                        : "border border-gray-200 text-gray-600 hover:border-gray-300"
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

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-gray-900">Tes obligations</h2>
          <button
            type="button"
            onClick={handleRecalculer}
            disabled={isRecalculating}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
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
 */
function ObligationItem({
  obligation,
  onToggle,
}: {
  obligation: ProjectRgpdObligationRead
  onToggle: (obligation: ProjectRgpdObligationRead) => void
}) {
  return (
    <li className="flex items-start gap-3 rounded-lg border border-gray-200 bg-white p-4">
      <input
        type="checkbox"
        checked={obligation.statut === "fait"}
        onChange={() => onToggle(obligation)}
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
 */
function AipdObligationItem({
  obligation,
  onToggle,
}: {
  obligation: ProjectRgpdObligationRead
  onToggle: (obligation: ProjectRgpdObligationRead) => void
}) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={obligation.statut === "fait"}
          onChange={() => onToggle(obligation)}
          className="mt-1 h-4 w-4 shrink-0 rounded border-amber-300 text-amber-600 focus:ring-amber-500"
        />
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-sm font-medium ${
                obligation.statut === "fait" ? "text-amber-400 line-through" : "text-amber-900"
              }`}
            >
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
