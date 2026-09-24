import { useState } from "react"
import { useOutletContext } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  finalizeDocumentGeneration,
  getCurrentSection,
  getDocumentPreview,
  goToPreviousSection,
  GuardrailError,
  restartDocumentGeneration,
  submitSection,
  type DocumentGenerationDocumentType,
  type GeneratedDocumentRead,
  type GuardrailBlockedDetail,
  type SectionAnswerSubmit,
  type SectionStateRead,
} from "../api/documentGenerationApi"
import { getAssociates, updateAssociateFondateur, type ProjectAssociateRead } from "../api/projectApi"
import PacteDocumentPreviewV2 from "../components/pacteFondateursV2/PacteDocumentPreviewV2"
import PacteFoundersSelectionV2 from "../components/pacteFondateursV2/PacteFoundersSelectionV2"
import PacteSectionFormV2 from "../components/pacteFondateursV2/PacteSectionFormV2"
import PacteGuardrailNotice from "../components/pacteFondateurs/PacteGuardrailNotice"
import PacteFondateurCopilotWidget from "../pacteFondateurCopilot/PacteFondateurCopilotWidget"
import PacteWelcomeStep from "../components/pacteFondateurs/PacteWelcomeStep"
import type { MyProjectOutletContext } from "./MyProjectLayout"

const DOCUMENT_TYPE: DocumentGenerationDocumentType = "pacte_fondateurs" // RENOMME (26/09/2026) : etait "pacte_fondateurs_v2" -- le v1 a ete supprime de la base, une seule version existe desormais.

type Phase = "welcome" | "loading" | "founders_selection" | "in_progress" | "finalized"

/**
 * Service 1.1.13 — Pacte de fondateurs, v2 (Groupe 5). Même scénario
 * fonctionnel et mêmes 2 volets synchronisés que `PacteFondateursPage` (v1),
 * mais le volet droit est ici un vrai PDF navigable (`PacteDocumentPreviewV2`,
 * react-pdf) rechargé depuis `GET .../preview` après chaque section validée
 * — plus de reconstruction du texte des clauses côté client (v1 le faisait
 * via `renderClauseTexte`, devenu inutile puisque le backend expose
 * maintenant un rendu PDF à la demande, jamais persisté avant la
 * finalisation, voir `document_generation_service.get_document_preview_pdf`).
 *
 * `PacteWelcomeStep` et `PacteGuardrailNotice` sont réutilisés tels quels
 * depuis `pacteFondateurs/` (v1) : génériques, aucune dépendance à
 * `document_type`, rien à forker (voir la règle actée le 21/09/2026 — on ne
 * forke que ce qu'on modifie réellement). `PacteSectionFormV2` (radio pour
 * `choix`), `PacteDocumentPreviewV2` (PDF) et `PacteFoundersSelectionV2`
 * (ci-dessous) sont les forks/ajouts v2.
 *
 * `founders_selection` (discussion du 21/09/2026) : juste après "Commencer",
 * si le projet a des associés marqués "partie au pacte", on demande de
 * choisir lesquels sont Fondateurs (vs Investisseurs) DANS le flux, plutôt
 * que de renvoyer l'utilisateur éditer `est_fondateur` associé par associé
 * dans "Équipe & capital" — remplace l'ancienne bannière passive qui se
 * contentait de signaler le préremplissage sans donner de prise dessus.
 *
 * CONSOLIDATION (27/09/2026, service 1.1.15) : cette page a porté 3
 * mécanismes d'explication IA construits successivement (icône par titre de
 * clause, historique des sections déjà rédigées, copilot) — retour "jury"
 * de l'utilisateur : trop de chemins concurrents pour une même action,
 * panneau gauche surchargé. Les 2 premiers sont retirés ; le copilot
 * (déjà existant, plus riche) reste l'unique point d'entrée, à la fois pour
 * les questions libres ET pour l'explication automatique poussée à chaque
 * nouvelle section (voir `copilotClauseContexte` et
 * PacteFondateurCopilotWidget.tsx).
 */
export default function PacteFondateursV2Page() {
  const { accessToken } = useAuth()
  const { project } = useOutletContext<MyProjectOutletContext>()

  const [phase, setPhase] = useState<Phase>("welcome")
  const [currentSection, setCurrentSection] = useState<SectionStateRead | null>(null)
  const [pacteAssociates, setPacteAssociates] = useState<ProjectAssociateRead[]>([])

  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [guardrailDetail, setGuardrailDetail] = useState<GuardrailBlockedDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [generatedDocument, setGeneratedDocument] = useState<GeneratedDocumentRead | null>(null)

  async function refreshPreview() {
    if (!accessToken) return
    setIsPreviewLoading(true)
    try {
      const blob = await getDocumentPreview(accessToken, project.id, DOCUMENT_TYPE)
      setPdfBlob(blob)
    } catch {
      // Aperçu best-effort : une erreur ici n'empêche pas de continuer le
      // questionnaire (le volet gauche reste la source de vérité), on ne
      // bloque pas l'utilisateur pour un rafraîchissement d'aperçu raté.
    } finally {
      setIsPreviewLoading(false)
    }
  }

  async function loadFirstSection() {
    if (!accessToken) return
    const section = await getCurrentSection(accessToken, project.id, DOCUMENT_TYPE)
    setCurrentSection(section)
    setPhase("in_progress")
    refreshPreview()
  }

  async function handleStart() {
    if (!accessToken) return
    setPhase("loading")
    setError(null)
    try {
      const associates = await getAssociates(accessToken, project.id)
      const partiesAuPacte = associates.filter((a) => a.est_partie_au_pacte_fondateurs)

      if (partiesAuPacte.length > 0) {
        setPacteAssociates(partiesAuPacte)
        setPhase("founders_selection")
        return
      }

      // Aucun associé "partie au pacte" — rien à choisir, on part directement
      // sur la 1ère section (le backend refusera au moment voulu si le pacte
      // a vraiment besoin d'au moins une partie, voir InvalidAnswerError côté
      // _render_identification_parties_v2).
      await loadFirstSection()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de démarrer la génération du pacte.")
      setPhase("welcome")
    }
  }

  async function handleConfirmFounders(fondateurIds: Set<string>) {
    if (!accessToken) return
    setError(null)
    setIsSubmitting(true)
    try {
      // Un PATCH seulement pour les associés dont la valeur change réellement
      // — pas la peine de réécrire ceux déjà à jour.
      const updates = pacteAssociates
        .filter((a) => fondateurIds.has(a.id) !== a.est_fondateur)
        .map((a) => updateAssociateFondateur(accessToken, project.id, a.id, fondateurIds.has(a.id)))
      await Promise.all(updates)
      await loadFirstSection()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'enregistrer les fondateurs sélectionnés.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleBackSection() {
    if (!accessToken) return
    setGuardrailDetail(null)
    setError(null)
    setIsSubmitting(true)
    try {
      const previous = await goToPreviousSection(accessToken, project.id, DOCUMENT_TYPE)
      setCurrentSection(previous)
      refreshPreview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de revenir à la section précédente.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleSubmitSection(body: SectionAnswerSubmit) {
    if (!accessToken || !currentSection?.code_section) return
    setGuardrailDetail(null)
    setError(null)
    setIsSubmitting(true)
    try {
      await submitSection(accessToken, project.id, DOCUMENT_TYPE, currentSection.code_section, body)

      const next = await getCurrentSection(accessToken, project.id, DOCUMENT_TYPE)
      setCurrentSection(next)
      refreshPreview()
    } catch (err) {
      if (err instanceof GuardrailError) {
        setGuardrailDetail(err.detail)
      } else {
        setError(err instanceof ApiError ? err.message : "Une erreur est survenue lors de l'enregistrement.")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleRestart() {
    if (!accessToken) return
    setError(null)
    setIsSubmitting(true)
    try {
      const section = await restartDocumentGeneration(accessToken, project.id, DOCUMENT_TYPE)
      setCurrentSection(section)
      refreshPreview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de recréer un nouveau pacte.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleFinalize() {
    if (!accessToken) return
    setError(null)
    setIsSubmitting(true)
    try {
      const document = await finalizeDocumentGeneration(accessToken, project.id, DOCUMENT_TYPE)
      setGeneratedDocument(document)
      setPhase("finalized")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de finaliser le document.")
    } finally {
      setIsSubmitting(false)
    }
  }

  // Contexte transmis au copilot (service 1.1.13, categorie 3) -- seulement
  // pendant la redaction d'une section active, jamais en dehors (welcome,
  // selection des fondateurs, finalisation) : le copilot répond alors sur le
  // pacte en general, sans clause precise en tete. `variables` (nom
  // technique + libelle) filtre les types jamais visibles utilisateur
  // (reference_croisee, auto_*) -- memes exclusions que le formulaire de
  // section lui-meme, voir ClauseVariable dans documentGenerationApi.ts.
  // Le nom technique est necessaire (pas seulement le libelle) : voir la
  // docstring de buildSuggestions() dans PacteFondateurCopilotWidget.tsx --
  // sans lui, le LLM devait deviner nom_variable et se trompait.
  const clauseEnCours = phase === "in_progress" && currentSection?.statut === "en_cours" ? currentSection.clause : null
  const copilotClauseContexte = clauseEnCours
    ? {
        code_clause: clauseEnCours.code_clause,
        titre_clause: clauseEnCours.titre_clause,
        variables: clauseEnCours.variables_requises
          .filter((v) => v.type !== "reference_croisee" && !v.type.startsWith("auto_"))
          .map((v) => ({ nom: v.nom, libelle: v.libelle })),
        // AJOUT (27/09/2026, service 1.1.15) — nécessaires pour que le
        // widget puisse pousser automatiquement une explication de CETTE
        // clause (POST .../auto-explication, voir sa docstring). documentType
        // constant ici, mais gardé explicite plutôt que codé en dur dans le
        // widget : celui-ci n'a pas à connaître DOCUMENT_TYPE de cette page.
        documentType: DOCUMENT_TYPE,
        codeSection: currentSection?.code_section ?? "",
      }
    : null

  return (
    // Même exemption de largeur/hauteur que v1 — voir "pacte-fondateurs-v2"
    // dans FULL_WIDTH_ROUTES (DashboardLayout.tsx).
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      <div className="flex w-1/2 flex-col gap-4 overflow-y-auto rounded-xl border border-gray-200 bg-gray-50 p-6">
        <h1 className="text-xl font-semibold text-gray-900">Pacte de fondateurs</h1>

        {phase === "welcome" && <PacteWelcomeStep onStart={handleStart} />}

        {phase === "loading" && <LoadingSpinner />}

        {error && <p className="text-sm text-red-600">{error}</p>}

        {phase === "founders_selection" && (
          <PacteFoundersSelectionV2
            associates={pacteAssociates}
            isSubmitting={isSubmitting}
            onConfirm={handleConfirmFounders}
          />
        )}

        {phase === "in_progress" && currentSection && currentSection.statut === "en_cours" && (
          <>
            {guardrailDetail && <PacteGuardrailNotice detail={guardrailDetail} />}
            <PacteSectionFormV2
              key={currentSection.code_section ?? "section"}
              section={currentSection}
              isSubmitting={isSubmitting}
              onSubmit={handleSubmitSection}
              onBack={handleBackSection}
            />
          </>
        )}

        {phase === "in_progress" && currentSection?.statut === "complete" && currentSection.document_deja_genere && (
          // 24/09/2026 : une session est unique par (projet, document_type) —
          // sans cette branche, revenir ici après une finalisation déjà faite
          // (ex. lors d'une visite précédente) réaffichait "Finaliser le
          // pacte", dont le clic échouait (SessionAlreadyCompleteError),
          // sans que rien n'explique pourquoi. Voir go_to_previous_section
          // pour l'alternative "reculer" et restart_session pour celle-ci.
          <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p className="text-sm text-blue-800">
              Un pacte de fondateurs a déjà été généré pour ce projet. Retrouve-le dans le coffre-fort documentaire,
              ou recrée un nouveau pacte depuis le début (le document déjà généré n'est pas supprimé).
            </p>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleRestart}
              className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Préparation…" : "Recréer un nouveau pacte"}
            </button>
          </div>
        )}

        {phase === "in_progress" && currentSection?.statut === "complete" && !currentSection.document_deja_genere && (
          <div className="flex flex-col gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-sm text-green-800">
              Toutes les sections du pacte sont rédigées. Relis le document dans le volet de droite, puis
              finalise-le pour générer le fichier définitif.
            </p>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleFinalize}
              className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Finalisation…" : "Finaliser le pacte"}
            </button>
          </div>
        )}

        {phase === "finalized" && generatedDocument && (
          <div className="flex flex-col gap-2 rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-sm text-green-800">Le pacte de fondateurs a été généré avec succès.</p>
            <a
              href={generatedDocument.secure_url}
              target="_blank"
              rel="noreferrer"
              className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
            >
              Ouvrir {generatedDocument.original_filename}
            </a>
          </div>
        )}
      </div>

      <div className="w-1/2 overflow-hidden rounded-xl border border-gray-200 bg-white">
        <PacteDocumentPreviewV2 pdfBlob={pdfBlob} isLoading={isPreviewLoading} />
      </div>

      {/* Montee une seule fois, en dehors du bloc conditionne par `phase` --
          voir la docstring de PacteFondateurCopilotWidget pour le pourquoi
          (etat ouvert/ferme + scroll ne doivent pas se reinitialiser a
          chaque changement de phase). */}
      <PacteFondateurCopilotWidget projectId={project.id} clauseContexte={copilotClauseContexte} />
    </div>
  )
}
