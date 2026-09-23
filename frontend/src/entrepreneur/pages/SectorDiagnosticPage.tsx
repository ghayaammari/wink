import { Fragment, useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import ComplianceScoreBadge from "../components/compliance/ComplianceScoreBadge"
import { useCopilot } from "../context/CopilotContext"
import { useAuth } from "../../shared/context/AuthContext"
import { getMyProject } from "../api/projectApi"
import {
  generateFintechGapAnalysis,
  generateHealthtechGapAnalysisChapitre,
  getFintechClassification,
  getFintechGapAnalysis,
  getFintechGapAnalysisScore,
  getFintechProfile,
  getHealthtechClassification,
  getHealthtechGapAnalysis,
  getHealthtechGapAnalysisScore,
  getHealthtechProfile,
  getSectorDetection,
  runSectorDetection,
  toggleFintechObligation,
  toggleHealthtechObligation,
  updateFintechProfile,
  updateHealthtechProfile,
  type ChapitreGapAnalysisStatusRead,
  type ChapitreHealthtech,
  type ClasseRisqueHealthtech,
  type ComplianceScoreRead,
  type FintechDataProfileRead,
  type HealthtechDataProfileRead,
  type ProjectFintechClassificationRead,
  type ProjectFintechGapAnalysisRead,
  type ProjectHealthtechClassificationRead,
  type ProjectSectorDetectionRead,
  type SecteurDetecte,
  type TypeAgrementFintech,
} from "../api/sectorApi"

type LoadState = "loading" | "ready" | "no_project" | "error"

type HealthtechField =
  | "est_dispositif_medical"
  | "fournit_aide_decision_diagnostique_ou_therapeutique"
  | "risque_deces_ou_deterioration_irreversible"
  | "risque_intervention_chirurgicale_ou_deterioration_grave"

type FintechField =
  | "gere_fonds_ou_paiements_clients"
  | "volume_mensuel_depasse_3_millions"
  | "propose_transmission_de_fonds"
  | "gere_investissement_ou_actifs"

// Texte des questions dupliqué depuis les `Field(description=...)` des
// schémas backend (source de vérité), même convention que AiActDiagnosticPage.
const HEALTHTECH_QUESTIONS: { field: HealthtechField; texte: string }[] = [
  {
    field: "est_dispositif_medical",
    texte:
      "Votre produit est-il un dispositif médical au sens réglementaire (destiné au diagnostic, à la prévention, au contrôle ou au traitement d'une maladie, d'une blessure ou d'un handicap) ?",
  },
  {
    field: "fournit_aide_decision_diagnostique_ou_therapeutique",
    texte:
      "Votre produit fournit-il une aide à la décision diagnostique ou thérapeutique (il analyse des données de santé pour orienter un diagnostic ou un traitement) ?",
  },
  {
    field: "risque_deces_ou_deterioration_irreversible",
    texte: "Une erreur de votre produit peut-elle entraîner un décès ou une détérioration irréversible de l'état de santé du patient ?",
  },
  {
    field: "risque_intervention_chirurgicale_ou_deterioration_grave",
    texte:
      "Une erreur de votre produit peut-elle nécessiter une intervention chirurgicale ou entraîner une détérioration grave de l'état de santé du patient ?",
  },
]

const FINTECH_QUESTIONS: { field: FintechField; texte: string }[] = [
  {
    field: "gere_fonds_ou_paiements_clients",
    texte: "Votre projet détient-il, gère-t-il ou transmet-il des fonds ou des paiements pour le compte de vos clients ?",
  },
  {
    field: "volume_mensuel_depasse_3_millions",
    texte: "Le volume mensuel des paiements traités dépasse-t-il 3 millions d'euros ?",
  },
  {
    field: "propose_transmission_de_fonds",
    texte:
      "Proposez-vous un service de transmission de fonds (envoi d'argent entre particuliers ou entreprises, sans tenir de compte de paiement) ?",
  },
  {
    field: "gere_investissement_ou_actifs",
    texte:
      "Votre projet gère-t-il de l'investissement ou des actifs pour le compte de vos clients (conseil en investissement, gestion de portefeuille, actifs numériques) ?",
  },
]

const SECTEUR_LABELS: Record<SecteurDetecte, string> = {
  healthtech: "HealthTech",
  fintech: "FinTech",
  aucun: "Aucun secteur réglementé détecté",
}

const CLASSE_RISQUE_LABELS: Record<ClasseRisqueHealthtech, string> = {
  non_dispositif_medical: "Non dispositif médical",
  I: "Classe I",
  IIa: "Classe IIa",
  IIb: "Classe IIb",
  III: "Classe III",
}

const TYPE_AGREMENT_LABELS: Record<TypeAgrementFintech, string> = {
  aucun: "Aucun agrément requis",
  agrement_simplifie: "Agrément simplifié",
  agrement_classique: "Agrément classique",
}

// Statut générique d'un noeud du chemin de conformité (classification OU
// chapitre d'analyse d'écart) — même 3 valeurs partout, dérivées côté
// backend (voir project_healthtech_gap_analysis_service.py /
// project_fintech_gap_analysis_service.py), jamais stockées séparément ici.
type NoeudStatut = "verrouille" | "debloque" | "fait"

// Identifiant d'un noeud du chemin : "classification", la clé d'un chapitre
// HealthTech, ou l'unique bloc FinTech.
type NoeudId = "classification" | ChapitreHealthtech | "fintech-gap-analysis"

interface NoeudData {
  id: NoeudId
  numero: number
  titre: string
  statut: NoeudStatut
}

const STATUT_NOEUD_LABELS: Record<NoeudStatut, string> = {
  verrouille: "Verrouillé",
  debloque: "À faire",
  fait: "Terminé",
}

const STATUT_NOEUD_STYLES: Record<NoeudStatut, string> = {
  verrouille: "border-gray-200 bg-gray-100 text-gray-400",
  debloque: "border-indigo-200 bg-indigo-50 text-indigo-800",
  fait: "border-emerald-200 bg-emerald-50 text-emerald-800",
}

function isHealthtechProfileComplete(profile: HealthtechDataProfileRead): boolean {
  return HEALTHTECH_QUESTIONS.every(({ field }) => profile[field] !== null)
}

function isFintechProfileComplete(profile: FintechDataProfileRead): boolean {
  return FINTECH_QUESTIONS.every(({ field }) => profile[field] !== null)
}

/**
 * Détail du service 3.3.5 (diagnostic de classification réglementaire) —
 * carte ouverte depuis CompliancePlanPage. Scope volontairement limité à 2
 * secteurs (HealthTech, FinTech), voir docstring backend
 * project_sector_detection.py.
 *
 * Le parcours de mise en conformité est un chemin HORIZONTAL de noeuds
 * (RoadmapPath, cercles reliés par un trait, scrollable si trop large) —
 * un seul noeud est "sélectionné" à la fois (selectedNodeId), et le contenu
 * affiché EN DESSOUS du chemin correspond uniquement au noeud sélectionné
 * (pas d'accordéon empilé, contrairement à une version précédente de cette
 * page) : cliquer sur un noeud débloqué/terminé remplace tout le panneau de
 * contenu, comme des onglets — pas de changement d'URL ni de navigateur
 * "back", choix explicite pour rester simple (voir conversation produit).
 * Un noeud verrouillé n'est pas cliquable (defense-in-depth : le backend
 * est la seule vraie source de vérité via ensure_chapitre_debloque /
 * ensure_classification_complete, le frontend grise juste par confort).
 * Aucun noeud n'est sélectionné par défaut à l'ouverture (selectedNodeId
 * démarre à `null`) : seul le chemin est visible tant que l'entrepreneur n'a
 * pas cliqué sur un noeud, contrairement à une version précédente qui
 * ouvrait "Profil réglementaire" automatiquement.
 * Le noeud "Profil réglementaire" se termine quand les 4 questions du
 * questionnaire ont une réponse (isHealthtechProfileComplete /
 * isFintechProfileComplete, calqué sur is_profile_complete côté backend) —
 * ça débloque alors le 1er chapitre d'analyse d'écart (HealthTech) ou
 * l'unique bloc (FinTech).
 *
 * Contrairement à AiActDiagnosticPage, pas de bouton "Recalculer" pour la
 * classification HealthTech/FinTech : chaque réponse au questionnaire
 * déclenche déjà le recalcul côté backend (calcul déterministe gratuit, voir
 * docstring project_healthtech_classification_service.py) — on recharge
 * juste la classification après chaque PATCH pour refléter le nouveau
 * résultat.
 *
 * Chaque obligation générée peut être cochée "accompli" par l'entrepreneur
 * (togglingObligation évite un double-clic pendant l'appel réseau) — pur
 * suivi manuel côté backend (toggle_obligation), sans lien avec le contenu
 * généré par le LLM. Une régénération du chapitre/bloc écrase ce suivi
 * (repasse tout à `false`), comme le reste du contenu du chapitre.
 */
export default function SectorDiagnosticPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const arriveDepuisCopilot = searchParams.get("from") === "copilot"
  const { addAssistantMessage } = useCopilot()
  const [state, setState] = useState<LoadState>("loading")
  const [projectId, setProjectId] = useState<string | null>(null)
  const [detection, setDetection] = useState<ProjectSectorDetectionRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isDetecting, setIsDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)

  const [healthtechProfile, setHealthtechProfile] = useState<HealthtechDataProfileRead | null>(null)
  const [healthtechClassification, setHealthtechClassification] = useState<ProjectHealthtechClassificationRead | null>(
    null,
  )
  const [fintechProfile, setFintechProfile] = useState<FintechDataProfileRead | null>(null)
  const [fintechClassification, setFintechClassification] = useState<ProjectFintechClassificationRead | null>(null)
  const [savingField, setSavingField] = useState<HealthtechField | FintechField | null>(null)

  const [healthtechGapAnalysis, setHealthtechGapAnalysis] = useState<ChapitreGapAnalysisStatusRead[] | null>(null)
  const [healthtechScore, setHealthtechScore] = useState<ComplianceScoreRead | null>(null)
  const [generatingChapitre, setGeneratingChapitre] = useState<ChapitreHealthtech | null>(null)
  const [gapAnalysisError, setGapAnalysisError] = useState<string | null>(null)

  const [fintechGapAnalysis, setFintechGapAnalysis] = useState<ProjectFintechGapAnalysisRead | null>(null)
  const [fintechScore, setFintechScore] = useState<ComplianceScoreRead | null>(null)
  const [isGeneratingFintechGapAnalysis, setIsGeneratingFintechGapAnalysis] = useState(false)
  const [fintechGapAnalysisError, setFintechGapAnalysisError] = useState<string | null>(null)

  // Index de l'obligation en cours de bascule ("accompli"), pour désactiver
  // son bouton pendant l'appel réseau (évite un double-clic) — un seul à la
  // fois suffit, l'UI ne permet pas de cliquer deux obligations en parallèle.
  const [togglingObligationIndex, setTogglingObligationIndex] = useState<number | null>(null)

  // Noeud actuellement sélectionné dans le chemin horizontal — `null` par
  // défaut : aucun noeud ne s'ouvre tant que l'entrepreneur n'a pas cliqué
  // dessus (seul le chemin est visible à l'ouverture de la carte).
  const [selectedNodeId, setSelectedNodeId] = useState<NoeudId | null>(null)

  useEffect(() => {
    async function load() {
      if (!accessToken) return
      const project = await getMyProject(accessToken)
      if (!project) {
        setState("no_project")
        return
      }
      setProjectId(project.id)
      const currentDetection = await getSectorDetection(accessToken, project.id)
      setDetection(currentDetection)
      await loadSectorSpecificData(accessToken, project.id, currentDetection.secteur_detecte)
      setState("ready")
    }
    load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Impossible de charger la conformité sectorielle.")
      setState("error")
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne doit tourner qu'au montage / changement de token
  }, [accessToken])

  async function loadSectorSpecificData(token: string, pid: string, secteur: SecteurDetecte | null) {
    if (secteur === "healthtech") {
      const [profile, classification, gapAnalysis, score] = await Promise.all([
        getHealthtechProfile(token, pid),
        getHealthtechClassification(token, pid),
        getHealthtechGapAnalysis(token, pid),
        getHealthtechGapAnalysisScore(token, pid),
      ])
      setHealthtechProfile(profile)
      setHealthtechClassification(classification)
      setHealthtechGapAnalysis(gapAnalysis)
      setHealthtechScore(score)
    } else if (secteur === "fintech") {
      const [profile, classification, gapAnalysis, score] = await Promise.all([
        getFintechProfile(token, pid),
        getFintechClassification(token, pid),
        getFintechGapAnalysis(token, pid),
        getFintechGapAnalysisScore(token, pid),
      ])
      setFintechProfile(profile)
      setFintechClassification(classification)
      setFintechGapAnalysis(gapAnalysis)
      setFintechScore(score)
    }
  }

  function handleSelectNode(nodeId: NoeudId) {
    // Toggle : recliquer sur le noeud deja selectionne referme son contenu,
    // au lieu de le rouvrir sur le meme noeud (meme comportement que
    // PlanActionPage.handleSelectNode, voir ce fichier).
    setSelectedNodeId((current) => (current === nodeId ? null : nodeId))
  }

  async function handleDetecter() {
    if (!accessToken || !projectId) return
    setIsDetecting(true)
    setDetectError(null)
    try {
      const result = await runSectorDetection(accessToken, projectId)
      setDetection(result)
      await loadSectorSpecificData(accessToken, projectId, result.secteur_detecte)
    } catch (err) {
      setDetectError(
        err instanceof ApiError
          ? "La détection du secteur a échoué, réessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setIsDetecting(false)
    }
  }

  async function handleAnswerHealthtech(field: HealthtechField, value: boolean | null) {
    if (!accessToken || !projectId) return
    setSavingField(field)
    try {
      const updated = await updateHealthtechProfile(accessToken, projectId, { [field]: value })
      setHealthtechProfile(updated)
      setHealthtechClassification(await getHealthtechClassification(accessToken, projectId))
      // Le déblocage du 1er chapitre dépend de la complétude du questionnaire
      // (voir docstring de la page) : on recharge la liste des chapitres pour
      // refléter un éventuel changement de statut "verrouille" -> "debloque".
      setHealthtechGapAnalysis(await getHealthtechGapAnalysis(accessToken, projectId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la réponse.")
    } finally {
      setSavingField(null)
    }
  }

  async function handleGenererChapitre(chapitre: ChapitreHealthtech) {
    if (!accessToken || !projectId) return
    setGeneratingChapitre(chapitre)
    setGapAnalysisError(null)
    try {
      // Le backend recalcule le statut de TOUS les chapitres après une
      // génération (le suivant peut passer de "verrouille" à "debloque") —
      // on recharge donc la liste entière plutôt que de patcher une seule
      // entrée localement, pour rester fidèle à l'état serveur.
      await generateHealthtechGapAnalysisChapitre(accessToken, projectId, chapitre)
      const statuses = await getHealthtechGapAnalysis(accessToken, projectId)
      setHealthtechGapAnalysis(statuses)
      setHealthtechScore(await getHealthtechGapAnalysisScore(accessToken, projectId))
      // Passe automatiquement au chapitre suivant nouvellement débloqué,
      // pour prolonger la sensation de "chemin qui avance" au clic.
      const indexCourant = statuses.findIndex((s) => s.cle === chapitre)
      const suivant = statuses[indexCourant + 1]
      if (suivant && suivant.statut === "debloque") {
        setSelectedNodeId(suivant.cle)
      }
    } catch (err) {
      setGapAnalysisError(
        err instanceof ApiError
          ? "La génération de ce chapitre a échoué, réessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setGeneratingChapitre(null)
    }
  }

  async function handleAnswerFintech(field: FintechField, value: boolean | null) {
    if (!accessToken || !projectId) return
    setSavingField(field)
    try {
      const updated = await updateFintechProfile(accessToken, projectId, { [field]: value })
      setFintechProfile(updated)
      setFintechClassification(await getFintechClassification(accessToken, projectId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer la réponse.")
    } finally {
      setSavingField(null)
    }
  }

  async function handleGenererFintechGapAnalysis() {
    if (!accessToken || !projectId) return
    setIsGeneratingFintechGapAnalysis(true)
    setFintechGapAnalysisError(null)
    try {
      setFintechGapAnalysis(await generateFintechGapAnalysis(accessToken, projectId))
      setFintechScore(await getFintechGapAnalysisScore(accessToken, projectId))
    } catch (err) {
      setFintechGapAnalysisError(
        err instanceof ApiError ? "La génération a échoué, réessaie dans quelques instants." : "Une erreur est survenue.",
      )
    } finally {
      setIsGeneratingFintechGapAnalysis(false)
    }
  }

  async function handleToggleHealthtechObligation(chapitre: ChapitreHealthtech, obligationIndex: number, accompli: boolean) {
    if (!accessToken || !projectId) return
    setTogglingObligationIndex(obligationIndex)
    setGapAnalysisError(null)
    try {
      await toggleHealthtechObligation(accessToken, projectId, chapitre, obligationIndex, accompli)
      setHealthtechGapAnalysis(await getHealthtechGapAnalysis(accessToken, projectId))
      setHealthtechScore(await getHealthtechGapAnalysisScore(accessToken, projectId))
    } catch (err) {
      setGapAnalysisError(err instanceof ApiError ? err.message : "Impossible d'enregistrer ce suivi.")
    } finally {
      setTogglingObligationIndex(null)
    }
  }

  async function handleToggleFintechObligation(obligationIndex: number, accompli: boolean) {
    if (!accessToken || !projectId) return
    setTogglingObligationIndex(obligationIndex)
    setFintechGapAnalysisError(null)
    try {
      setFintechGapAnalysis(await toggleFintechObligation(accessToken, projectId, obligationIndex, accompli))
      setFintechScore(await getFintechGapAnalysisScore(accessToken, projectId))
    } catch (err) {
      setFintechGapAnalysisError(err instanceof ApiError ? err.message : "Impossible d'enregistrer ce suivi.")
    } finally {
      setTogglingObligationIndex(null)
    }
  }

  if (state === "loading") return <LoadingSpinner />
  if (state === "error") return <p className="text-sm text-red-600">{error}</p>
  if (state === "no_project") {
    return <p className="text-sm text-gray-500">Termine d'abord l'onboarding pour accéder à cette section.</p>
  }
  if (!detection) return null

  const secteur = detection.secteur_detecte

  function handleTerminer() {
    // Ne telecharge plus rien ici (voir CopilotContext.tsx) : le rapport
    // n'est genere/telecharge qu'au clic sur le bouton correspondant dans
    // le chat du copilot, jamais automatiquement au clic sur "Terminer".
    if (secteur !== "healthtech" && secteur !== "fintech") return
    let scoreTexte = "non disponible (aucune obligation évaluée)"
    if (secteur === "healthtech" && healthtechScore?.score !== undefined && healthtechScore.score !== null) {
      scoreTexte = `${healthtechScore.score}%`
    } else if (secteur === "fintech" && fintechScore?.score !== undefined && fintechScore.score !== null) {
      scoreTexte = `${fintechScore.score}%`
    }
    addAssistantMessage(`Conformite sectorielle terminee. Score de conformite final : ${scoreTexte}.`, secteur)
    navigate("/entrepreneur/copilot")
  }

  const classificationComplete =
    secteur === "healthtech"
      ? healthtechProfile !== null && isHealthtechProfileComplete(healthtechProfile)
      : secteur === "fintech"
        ? fintechProfile !== null && isFintechProfileComplete(fintechProfile)
        : false

  // Renommé depuis "Classification" : ce noeud est le questionnaire qui
  // PRODUIT la classification (classe de risque / type d'agrément), le nom
  // reflète mieux ce que l'entrepreneur y fait concrètement.
  const classificationNode: NoeudData = {
    id: "classification",
    numero: 1,
    titre: "Profil réglementaire",
    statut: classificationComplete ? "fait" : "debloque",
  }

  // Liste des noeuds du chemin, dans l'ordre — construite selon le secteur
  // (HealthTech : classification + 3 chapitres MDR ; FinTech : classification
  // + bloc unique). Vide si healthtechGapAnalysis n'est pas encore chargé,
  // pour ne montrer que "Profil réglementaire" pendant ce court instant
  // plutôt qu'un chemin incomplet.
  const roadmapNodes: NoeudData[] =
    secteur === "healthtech"
      ? [
          classificationNode,
          ...(healthtechGapAnalysis ?? []).map(
            (chapitreStatus, index): NoeudData => ({
              id: chapitreStatus.cle,
              numero: index + 2,
              titre: chapitreStatus.titre,
              statut: chapitreStatus.statut,
            }),
          ),
        ]
      : secteur === "fintech"
        ? [
            classificationNode,
            {
              id: "fintech-gap-analysis",
              numero: 2,
              titre: "Analyse d'écart",
              statut: fintechGapAnalysis !== null ? "fait" : classificationComplete ? "debloque" : "verrouille",
            },
          ]
        : []

  // Pas de fallback sur roadmapNodes[0] : tant que selectedNodeId est
  // `null` (état initial, ou après un changement de secteur), aucun panneau
  // de contenu ne s'affiche sous le chemin.
  const selectedNode = selectedNodeId === null ? null : roadmapNodes.find((node) => node.id === selectedNodeId) ?? null

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold text-gray-900">Conformité sectorielle</h1>
          <p className="text-sm text-gray-500">
            Détecte si ton projet relève d'un secteur réglementé (HealthTech ou FinTech) et suis le parcours de mise
            en conformité correspondant.
          </p>
        </div>
        {arriveDepuisCopilot && (secteur === "healthtech" || secteur === "fintech") && (
          <button
            type="button"
            onClick={handleTerminer}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100"
          >
            Terminer et revenir au copilot
          </button>
        )}
      </div>

      <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-gray-900">Secteur détecté</h2>
          <button
            type="button"
            onClick={handleDetecter}
            disabled={isDetecting}
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
          >
            {isDetecting ? "Détection en cours..." : secteur === null ? "Détecter mon secteur" : "Redétecter mon secteur"}
          </button>
        </div>

        {detectError && <p className="text-sm text-red-600">{detectError}</p>}

        {secteur === null ? (
          <p className="text-sm text-gray-500">
            Aucune détection lancée pour l'instant — clique sur "Détecter mon secteur".
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            <span className="w-fit rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-indigo-800">
              {SECTEUR_LABELS[secteur]}
            </span>
            {detection.justification && <p className="text-sm text-gray-700">{detection.justification}</p>}
          </div>
        )}
      </div>

      {roadmapNodes.length > 0 && (
        <div className="flex flex-col gap-4">
          <h2 className="text-base font-semibold text-gray-900">Parcours de mise en conformité</h2>

          {secteur === "healthtech" && healthtechScore && (
            <ComplianceScoreBadge score={healthtechScore.score} totalObligations={healthtechScore.total_obligations} />
          )}
          {secteur === "fintech" && fintechScore && (
            <ComplianceScoreBadge score={fintechScore.score} totalObligations={fintechScore.total_obligations} />
          )}

          <RoadmapPath nodes={roadmapNodes} selectedId={selectedNodeId} onSelect={handleSelectNode} />

          {selectedNode && (
            <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-gray-900">{selectedNode.titre}</h3>
                <span
                  className={`w-fit rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${STATUT_NOEUD_STYLES[selectedNode.statut]}`}
                >
                  {STATUT_NOEUD_LABELS[selectedNode.statut]}
                </span>
              </div>

              {selectedNode.statut === "verrouille" ? (
                <p className="text-sm text-gray-400">Termine d'abord l'étape précédente pour débloquer celle-ci.</p>
              ) : selectedNodeId === "classification" ? (
                <div className="flex flex-col gap-3">
                  {secteur === "healthtech" &&
                    healthtechProfile &&
                    HEALTHTECH_QUESTIONS.map(({ field, texte }) => (
                      <QuestionCard
                        key={field}
                        field={field}
                        texte={texte}
                        value={healthtechProfile[field]}
                        isSaving={savingField === field}
                        onAnswer={handleAnswerHealthtech}
                      />
                    ))}
                  {secteur === "fintech" &&
                    fintechProfile &&
                    FINTECH_QUESTIONS.map(({ field, texte }) => (
                      <QuestionCard
                        key={field}
                        field={field}
                        texte={texte}
                        value={fintechProfile[field]}
                        isSaving={savingField === field}
                        onAnswer={handleAnswerFintech}
                      />
                    ))}

                  {secteur === "healthtech" && healthtechClassification && (
                    <ClassificationResult
                      label={
                        healthtechClassification.classe_risque === null
                          ? null
                          : CLASSE_RISQUE_LABELS[healthtechClassification.classe_risque]
                      }
                      justification={healthtechClassification.justification}
                    />
                  )}
                  {secteur === "fintech" && fintechClassification && (
                    <ClassificationResult
                      label={
                        fintechClassification.type_agrement === null
                          ? null
                          : TYPE_AGREMENT_LABELS[fintechClassification.type_agrement]
                      }
                      justification={fintechClassification.justification}
                    />
                  )}
                </div>
              ) : selectedNodeId === "fintech-gap-analysis" ? (
                <FintechGapAnalysisContent
                  resultat={fintechGapAnalysis}
                  isGenerating={isGeneratingFintechGapAnalysis}
                  error={fintechGapAnalysisError}
                  onGenerer={handleGenererFintechGapAnalysis}
                  togglingIndex={togglingObligationIndex}
                  onToggleObligation={handleToggleFintechObligation}
                />
              ) : (
                healthtechGapAnalysis &&
                (() => {
                  const chapitreStatus = healthtechGapAnalysis.find((c) => c.cle === selectedNodeId)
                  if (!chapitreStatus) return null
                  return (
                    <>
                      {gapAnalysisError && <p className="text-sm text-red-600">{gapAnalysisError}</p>}
                      <GapAnalysisChapitreContent
                        chapitreStatus={chapitreStatus}
                        isGenerating={generatingChapitre === chapitreStatus.cle}
                        onGenerer={handleGenererChapitre}
                        togglingIndex={togglingObligationIndex}
                        onToggleObligation={handleToggleHealthtechObligation}
                      />
                    </>
                  )
                })()
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Chemin HORIZONTAL de noeuds (cercles reliés par un trait), scrollable
 * horizontalement si trop large pour l'écran. Cliquer sur un noeud
 * débloqué/terminé le sélectionne (le contenu affiché en dessous, dans le
 * parent, change en conséquence) — un noeud verrouillé n'est pas cliquable.
 * `selectedId` peut être `null` (aucun noeud sélectionné, état initial) :
 * dans ce cas aucun cercle n'affiche le style "sélectionné".
 */
function RoadmapPath({
  nodes,
  selectedId,
  onSelect,
}: {
  nodes: NoeudData[]
  selectedId: NoeudId | null
  onSelect: (id: NoeudId) => void
}) {
  return (
    <div className="flex items-start gap-2 overflow-x-auto pb-2">
      {nodes.map((node, index) => {
        const estVerrouille = node.statut === "verrouille"
        const estFait = node.statut === "fait"
        const estSelectionne = node.id === selectedId

        return (
          <Fragment key={node.id}>
            {index > 0 && (
              <div
                className={`mt-4 h-px w-8 shrink-0 sm:w-16 ${nodes[index - 1].statut === "fait" ? "bg-emerald-300" : "bg-gray-200"}`}
              />
            )}
            <button
              type="button"
              disabled={estVerrouille}
              onClick={() => onSelect(node.id)}
              className="flex w-24 shrink-0 flex-col items-center gap-1.5 text-center disabled:cursor-not-allowed"
            >
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition ${
                  estFait
                    ? "bg-emerald-600 text-white"
                    : estVerrouille
                      ? "cursor-not-allowed bg-gray-200 text-gray-400"
                      : estSelectionne
                        ? "bg-indigo-600 text-white ring-2 ring-indigo-200 ring-offset-2"
                        : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
                }`}
              >
                {estFait ? "✓" : node.numero}
              </span>
              <span className={`text-xs leading-tight ${estSelectionne ? "font-semibold text-gray-900" : estVerrouille ? "text-gray-400" : "text-gray-600"}`}>
                {node.titre}
              </span>
            </button>
          </Fragment>
        )
      })}
    </div>
  )
}

function ClassificationResult({ label, justification }: { label: string | null; justification: string | null }) {
  if (label === null) {
    return (
      <p className="text-sm text-gray-500">
        Réponds aux questions ci-dessus pour obtenir ta classification — elle se met à jour automatiquement.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-gray-50 p-4">
      <span className="w-fit rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-emerald-800">
        {label}
      </span>
      {justification && <p className="text-sm text-gray-700">{justification}</p>}
    </div>
  )
}

/**
 * Une question tri-état (Oui / Non / Pas encore répondu) — copie conforme du
 * composant homonyme de AiActDiagnosticPage, générique sur le type de champ
 * (HealthtechField | FintechField) pour être réutilisé pour les deux
 * secteurs sans dupliquer le JSX.
 */
function QuestionCard<TField extends string>({
  field,
  texte,
  value,
  isSaving,
  onAnswer,
}: {
  field: TField
  texte: string
  value: boolean | null
  isSaving: boolean
  onAnswer: (field: TField, value: boolean | null) => void
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

/**
 * Une obligation générée, cliquable pour basculer son suivi manuel
 * "accompli" (service 3.3.6) — se colore en vert une fois cochée. Pur
 * confort de suivi côté entrepreneur : ne redéclenche jamais le LLM, et une
 * régénération du chapitre/bloc écrase ce statut (repasse à `false`), voir
 * docstring de la page.
 */
function ObligationItem({
  nom,
  description,
  accompli,
  isToggling,
  onToggle,
}: {
  nom: string
  description: string
  accompli: boolean
  isToggling: boolean
  onToggle: () => void
}) {
  return (
    <li>
      <button
        type="button"
        disabled={isToggling}
        onClick={onToggle}
        className={`w-full rounded-lg border p-3 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
          accompli ? "border-emerald-300 bg-emerald-50" : "border-gray-200 bg-white hover:border-gray-300"
        }`}
      >
        <div className="flex items-start gap-2">
          <span
            className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold ${
              accompli ? "border-emerald-500 bg-emerald-500 text-white" : "border-gray-300 bg-white text-transparent"
            }`}
          >
            ✓
          </span>
          <div className="flex flex-col gap-0.5">
            <p className={`text-sm font-medium ${accompli ? "text-emerald-900" : "text-gray-900"}`}>{nom}</p>
            <p className={`text-sm ${accompli ? "text-emerald-800" : "text-gray-700"}`}>{description}</p>
          </div>
        </div>
      </button>
    </li>
  )
}

/**
 * Contenu du noeud d'un chapitre HealthTech (service 3.3.6) — un chapitre du
 * gap-analysis MDR. Le titre/statut sont déjà affichés par le panneau parent
 * : ce composant ne rend que le bouton Générer/Régénérer et les obligations
 * déjà générées (le backend écrase le résultat à chaque régénération, pas de
 * règle "jamais écraser un fait" ici, voir
 * project_healthtech_gap_analysis_service.py — ça vaut aussi pour le suivi
 * "accompli" de chaque obligation, remis à `false` à chaque régénération).
 */
function GapAnalysisChapitreContent({
  chapitreStatus,
  isGenerating,
  onGenerer,
  togglingIndex,
  onToggleObligation,
}: {
  chapitreStatus: ChapitreGapAnalysisStatusRead
  isGenerating: boolean
  onGenerer: (chapitre: ChapitreHealthtech) => void
  togglingIndex: number | null
  onToggleObligation: (chapitre: ChapitreHealthtech, obligationIndex: number, accompli: boolean) => void
}) {
  const { cle, statut, resultat } = chapitreStatus

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        disabled={isGenerating}
        onClick={() => onGenerer(cle)}
        className="w-fit rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
      >
        {isGenerating ? "Génération en cours..." : statut === "fait" ? "Régénérer" : "Générer"}
      </button>

      {resultat && (
        <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <p className="text-sm text-gray-700">{resultat.justification}</p>
          {resultat.obligations.obligations.length === 0 ? (
            <p className="text-xs text-gray-500">Aucune obligation identifiée pour ce chapitre.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {resultat.obligations.obligations.map((obligation, index) => (
                <ObligationItem
                  key={index}
                  nom={obligation.nom}
                  description={obligation.description}
                  accompli={obligation.accompli}
                  isToggling={togglingIndex === index}
                  onToggle={() => onToggleObligation(cle, index, !obligation.accompli)}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Contenu du noeud unique d'analyse d'écart FinTech — le titre/statut sont
 * déjà affichés par le panneau parent : juste le bouton générer/régénérer
 * et le résultat éventuel.
 */
function FintechGapAnalysisContent({
  resultat,
  isGenerating,
  error,
  onGenerer,
  togglingIndex,
  onToggleObligation,
}: {
  resultat: ProjectFintechGapAnalysisRead | null
  isGenerating: boolean
  error: string | null
  onGenerer: () => void
  togglingIndex: number | null
  onToggleObligation: (obligationIndex: number, accompli: boolean) => void
}) {
  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="button"
        disabled={isGenerating}
        onClick={onGenerer}
        className="w-fit rounded-lg bg-indigo-600 px-3 py-2 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
      >
        {isGenerating ? "Génération en cours..." : resultat ? "Régénérer" : "Générer"}
      </button>

      {resultat && (
        <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <p className="text-sm text-gray-700">{resultat.justification}</p>
          {resultat.obligations.obligations.length === 0 ? (
            <p className="text-xs text-gray-500">Aucune obligation identifiée.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {resultat.obligations.obligations.map((obligation, index) => (
                <ObligationItem
                  key={index}
                  nom={obligation.nom}
                  description={obligation.description}
                  accompli={obligation.accompli}
                  isToggling={togglingIndex === index}
                  onToggle={() => onToggleObligation(index, !obligation.accompli)}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
