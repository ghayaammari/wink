import { useEffect, useRef, useState } from "react"
import { useOutletContext } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  annulerCorrection,
  appliquerCorrection,
  finalizeDocumentGeneration,
  getCurrentSection,
  getDocumentPreview,
  getPrevalidation,
  getValidationFinale,
  goToPreviousSection,
  GuardrailError,
  restartDocumentGeneration,
  retirerFacultatif,
  rouvrirSection,
  submitFacultatifs,
  submitSection,
  type DocumentGenerationDocumentType,
  type GeneratedDocumentRead,
  type GuardrailBlockedDetail,
  type PrevalidationProbleme,
  type SectionAnswerSubmit,
  type ProblemeValidation,
  type SectionStateRead,
  type ValidationFinaleRead,
  ValidationFinaleBloqueeError,
} from "../api/documentGenerationApi"
import PacteDocumentPreviewV2 from "../components/pacteFondateursV2/PacteDocumentPreviewV2"
import PacteGuardrailNotice from "../components/pacteFondateurs/PacteGuardrailNotice"
import StatutsFacultatifsStep from "../components/statutsSas/StatutsFacultatifsStep"
import StatutsPrevalidationStep from "../components/statutsSas/StatutsPrevalidationStep"
import StatutsSectionForm from "../components/statutsSas/StatutsSectionForm"
import StatutsValidationFinaleStep from "../components/statutsSas/StatutsValidationFinaleStep"
import StatutsWelcomeStep from "../components/statutsSas/StatutsWelcomeStep"
import type { MyProjectOutletContext } from "./MyProjectLayout"

const DOCUMENT_TYPE: DocumentGenerationDocumentType = "statuts"

type Phase = "welcome" | "loading" | "prevalidation" | "in_progress" | "finalized"

/**
 * Service 1.1.4 — Statuts de la SAS. Fork de `PacteFondateursV2Page`
 * (service 1.1.13), même moteur de session générique côté backend
 * (document_generation_service.py), avec 2 différences fonctionnelles
 * assumées dès le départ (pas une omission) :
 *
 * - Pas de phase `founders_selection` : le préambule des statuts
 *   (`_render_identification_parties_statuts`) inclut automatiquement TOUS
 *   les associés `est_fondateur=True`, sans étape de sélection — contrairement
 *   au pacte, où Fondateurs/Investisseurs doivent être choisis avant de
 *   démarrer (voir PacteFoundersSelectionV2). "Commencer" mène donc
 *   directement à `loadFirstSection()`.
 * - Pas de copilot (PacteFondateurCopilotWidget) : ce widget est le service
 *   1.1.15 "Explication des clauses", construit spécifiquement pour le
 *   pacte (voir recap-service-1.1.13-copilot-pacte-fondateurs.md) — aucun
 *   équivalent n'existe encore pour les statuts. À ajouter séparément si ce
 *   service est étendu aux statuts, pas monté ici par anticipation.
 *
 * `PacteGuardrailNotice` et `PacteDocumentPreviewV2` sont réutilisés tels
 * quels (génériques, aucun texte propre au pacte) ; `StatutsWelcomeStep` et
 * `StatutsSectionForm` sont des forks dédiés (voir leurs docstrings).
 */
export default function StatutsSasPage() {
  const { accessToken } = useAuth()
  const { project } = useOutletContext<MyProjectOutletContext>()

  const [phase, setPhase] = useState<Phase>("welcome")
  // Pré-validation au démarrage (24/09/2026) : données du projet manquantes.
  const [problemesPrevalidation, setProblemesPrevalidation] = useState<PrevalidationProbleme[]>([])
  const [isRechecking, setIsRechecking] = useState(false)
  const [currentSection, setCurrentSection] = useState<SectionStateRead | null>(null)

  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [guardrailDetail, setGuardrailDetail] = useState<GuardrailBlockedDetail | null>(null)
  // Dernière saisie soumise : renvoyée telle quelle si l'utilisateur confirme
  // des avertissements (StatutsReglesNotice → « Continuer quand même »).
  const [derniereSaisie, setDerniereSaisie] = useState<SectionAnswerSubmit | null>(null)
  // Problèmes par champ (garde-fou des statuts, format `problemes`) :
  // affichés sous chaque champ par StatutsSectionForm, qui fait lui-même
  // défiler jusqu'au premier. Autre alerte (sans `problemes`) : affichée
  // sous le formulaire, on y fait défiler la page.
  const alerteRef = useRef<HTMLDivElement | null>(null)
  const alerteParChamp = guardrailDetail?.problemes ? guardrailDetail : null
  useEffect(() => {
    if (guardrailDetail && !guardrailDetail.problemes) {
      alerteRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
    }
  }, [guardrailDetail])

  /** L'utilisateur corrige un champ : son erreur disparaît aussitôt (pas de
   * message périmé à l'écran). Les autres restent jusqu'au prochain envoi. */
  function handleChampModifie(nom: string, associeId: string | null) {
    setGuardrailDetail((detail) => {
      if (!detail?.problemes) return detail
      const restants = detail.problemes.filter(
        (p) => !(p.variable === nom && (associeId === null || !p.associe_id || p.associe_id === associeId)),
      )
      if (restants.length === detail.problemes.length) return detail
      if (restants.length === 0) return null
      return {
        ...detail,
        problemes: restants,
        avertissements_seulement: restants.every((p) => p.gravite === "avertissement"),
      }
    })
  }
  const [error, setError] = useState<string | null>(null)

  const [generatedDocument, setGeneratedDocument] = useState<GeneratedDocumentRead | null>(null)

  // Vérification finale (24/09/2026) : lancée dès que toutes les sections
  // sont rédigées (y compris au retour d'une correction, qui se termine
  // toute seule), avant de pouvoir générer.
  const [validation, setValidation] = useState<ValidationFinaleRead | null>(null)
  const [isChecking, setIsChecking] = useState(false)
  const parcoursTermine =
    phase === "in_progress" && currentSection?.statut === "complete" && !currentSection.document_deja_genere

  async function verifierDocument() {
    if (!accessToken) return
    setIsChecking(true)
    setError(null)
    try {
      setValidation(await getValidationFinale(accessToken, project.id, DOCUMENT_TYPE))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de vérifier les statuts pour le moment.")
    } finally {
      setIsChecking(false)
    }
  }

  useEffect(() => {
    if (parcoursTermine) verifierDocument()
    else setValidation(null)
    // Relancée seulement quand le parcours (re)devient terminé.
  }, [parcoursTermine])

  /** « Corriger → » : rouvre la section ; les autres réponses sont gardées. */
  async function handleCorriger(codeSection: string) {
    if (!accessToken) return
    setError(null)
    setIsSubmitting(true)
    try {
      setCurrentSection(await rouvrirSection(accessToken, project.id, DOCUMENT_TYPE, codeSection))
      refreshPreview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de rouvrir cette section.")
    } finally {
      setIsSubmitting(false)
    }
  }

  /** « Appliquer » : enregistre la correction certaine, puis revérifie. */
  async function handleAppliquer(p: ProblemeValidation) {
    if (!accessToken || !p.cible || !p.valeur_a_appliquer) return
    setIsChecking(true)
    setError(null)
    try {
      await appliquerCorrection(accessToken, project.id, DOCUMENT_TYPE, { code_section: p.cible, ...p.valeur_a_appliquer })
      refreshPreview()
      setValidation(await getValidationFinale(accessToken, project.id, DOCUMENT_TYPE))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d'appliquer cette correction.")
    } finally {
      setIsChecking(false)
    }
  }

  /** « Revenir à la vérification » : annule la correction, sans rien changer. */
  async function handleAnnulerCorrection() {
    if (!accessToken) return
    setGuardrailDetail(null)
    setError(null)
    setIsSubmitting(true)
    try {
      setCurrentSection(await annulerCorrection(accessToken, project.id, DOCUMENT_TYPE))
      refreshPreview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de revenir à la vérification.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function refreshPreview() {
    if (!accessToken) return
    setIsPreviewLoading(true)
    try {
      const blob = await getDocumentPreview(accessToken, project.id, DOCUMENT_TYPE)
      setPdfBlob(blob)
    } catch {
      // Aperçu best-effort — voir PacteFondateursV2Page.refreshPreview.
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

  /** Pré-validation (24/09/2026) : bloque le démarrage tant que des données
   * du projet reprises automatiquement manquent -- voir
   * StatutsPrevalidationStep. Renvoie `true` si on peut commencer. */
  async function verifierPrevalidation(): Promise<boolean> {
    const resultat = await getPrevalidation(accessToken!, project.id, DOCUMENT_TYPE)
    setProblemesPrevalidation(resultat.problemes)
    return resultat.pret
  }

  async function handleStart() {
    if (!accessToken) return
    setPhase("loading")
    setError(null)
    try {
      if (!(await verifierPrevalidation())) {
        setPhase("prevalidation")
        return
      }
      await loadFirstSection()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de démarrer la rédaction des statuts.")
      setPhase("welcome")
    }
  }

  async function handleRecheckPrevalidation() {
    if (!accessToken) return
    setIsRechecking(true)
    setError(null)
    try {
      if (await verifierPrevalidation()) {
        setPhase("loading")
        await loadFirstSection()
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de vérifier les informations du projet.")
    } finally {
      setIsRechecking(false)
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
    setDerniereSaisie(body)
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

  // Audit #19 : écran de choix des facultatifs (pause avant l'Art. 8) et
  // bouton "Ne plus inclure cet article" — mêmes enchaînement et gestion
  // d'erreur que handleSubmitSection (appel, puis rechargement de l'état).
  async function runThenReload(action: () => Promise<unknown>, messageErreur: string) {
    if (!accessToken) return
    setGuardrailDetail(null)
    setError(null)
    setIsSubmitting(true)
    try {
      await action()
      const next = await getCurrentSection(accessToken, project.id, DOCUMENT_TYPE)
      setCurrentSection(next)
      refreshPreview()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : messageErreur)
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleSubmitFacultatifs(codesChoisis: string[]) {
    if (!accessToken) return
    runThenReload(
      () => submitFacultatifs(accessToken, project.id, DOCUMENT_TYPE, codesChoisis),
      "Impossible d'enregistrer le choix des articles facultatifs.",
    )
  }

  function handleRetirerFacultatif() {
    if (!accessToken) return
    runThenReload(
      () => retirerFacultatif(accessToken, project.id, DOCUMENT_TYPE),
      "Impossible de retirer cet article.",
    )
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
      setError(err instanceof ApiError ? err.message : "Impossible de recréer de nouveaux statuts.")
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
      if (err instanceof ValidationFinaleBloqueeError) {
        // Un point bloquant est apparu entre la vérification et le clic
        // (ex. dirigeant supprimé dans un autre onglet) : liste à jour.
        setValidation(err.validation)
      } else {
        setError(err instanceof ApiError ? err.message : "Impossible de finaliser le document.")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    // Même exemption de largeur que le pacte — voir "statuts" dans
    // FULL_WIDTH_ROUTES (DashboardLayout.tsx).
    <div className="flex h-[calc(100vh-8rem)] gap-6">
      <div className="flex w-1/2 flex-col gap-4 overflow-y-auto rounded-xl border border-gray-200 bg-gray-50 p-6">
        <h1 className="text-xl font-semibold text-gray-900">Statuts de la société</h1>

        {phase === "welcome" && <StatutsWelcomeStep onStart={handleStart} />}

        {phase === "loading" && <LoadingSpinner />}

        {phase === "prevalidation" && (
          <StatutsPrevalidationStep
            problemes={problemesPrevalidation}
            isChecking={isRechecking}
            onRecheck={handleRecheckPrevalidation}
            onBack={() => setPhase("welcome")}
          />
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        {phase === "in_progress" &&
          currentSection &&
          currentSection.statut === "en_cours" &&
          currentSection.choix_facultatifs_requis && (
            <StatutsFacultatifsStep
              titre={currentSection.titre_section}
              explication={currentSection.explication_section}
              facultatifs={currentSection.facultatifs ?? []}
              isSubmitting={isSubmitting}
              onSubmit={handleSubmitFacultatifs}
              onBack={handleBackSection}
            />
          )}

        {phase === "in_progress" &&
          currentSection &&
          currentSection.statut === "en_cours" &&
          !currentSection.choix_facultatifs_requis && (
            <>
              <StatutsSectionForm
                key={currentSection.code_section ?? "section"}
                section={currentSection}
                isSubmitting={isSubmitting}
                onSubmit={handleSubmitSection}
                onBack={handleBackSection}
                onRetirerFacultatif={handleRetirerFacultatif}
                alerte={alerteParChamp}
                onConfirmerAvertissements={() =>
                  derniereSaisie && handleSubmitSection({ ...derniereSaisie, confirmer_avertissements: true })
                }
                onChampModifie={handleChampModifie}
                onAnnulerCorrection={handleAnnulerCorrection}
              />
              {/* Alerte sans détail par champ (cas rare) : sous le formulaire. */}
              <div ref={alerteRef}>
                {guardrailDetail && !guardrailDetail.problemes && <PacteGuardrailNotice detail={guardrailDetail} />}
              </div>
            </>
          )}

        {phase === "in_progress" && currentSection?.statut === "complete" && currentSection.document_deja_genere && (
          <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p className="text-sm text-blue-800">
              Des statuts ont déjà été générés pour ce projet. Retrouve-les dans le coffre-fort documentaire, ou
              recrée de nouveaux statuts depuis le début (le document déjà généré n'est pas supprimé).
            </p>
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleRestart}
              className="self-start rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting ? "Préparation…" : "Recréer de nouveaux statuts"}
            </button>
          </div>
        )}

        {parcoursTermine && (
          <StatutsValidationFinaleStep
            validation={validation}
            isChecking={isChecking}
            isGenerating={isSubmitting}
            onRecheck={verifierDocument}
            onCorriger={handleCorriger}
            onAppliquer={handleAppliquer}
            onGenerer={handleFinalize}
          />
        )}

        {phase === "finalized" && generatedDocument && (
          <div className="flex flex-col gap-2 rounded-lg border border-green-200 bg-green-50 p-4">
            <p className="text-sm text-green-800">Les statuts ont été générés avec succès.</p>
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
    </div>
  )
}
