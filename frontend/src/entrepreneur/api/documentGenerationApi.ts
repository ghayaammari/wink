/**
 * Client HTTP pour `backend/entrepreneur/routes/document_generation_router.py`
 * — service 1.1.13 (pacte de fondateurs interactif, Groupe 5). Même convention
 * que roadmapApi.ts : accessToken en premier paramètre, `request<T>` local
 * (pas factorisé au-delà de ApiError, même choix que les autres `*Api.ts`).
 *
 * `document_type` est un paramètre de chaque fonction plutôt qu'une constante
 * figée sur "pacte_fondateurs" : ce moteur de session est explicitement conçu
 * côté backend pour être réutilisé tel quel par 1.1.4 (statuts) avec un autre
 * squelette de `document_templates` — voir document_generation_service.py.
 *
 * RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026) : `scenario` -> `code_clause`,
 * `scenario_description` -> `description_clause`, `nom_section` -> `code_section`,
 * `type_contenu` -> `comportement_section` — les champs JSON de l'API ont changé
 * de nom côté backend, ce fichier doit rester synchronisé (aucun alias Pydantic).
 */
import { ApiError } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type DocumentGenerationDocumentType = "pacte_fondateurs" | "statuts" // "pacte_fondateurs_v2" retire (26/09/2026) : v1 supprime, plus qu'une seule valeur pacte.

export type SectionComportement =
  | "mention_obligatoire"
  | "clause_optionnelle"
  | "variante_obligatoire"

export type VariableType =
  | "texte"
  | "nombre"
  | "montant"
  | "duree"
  | "date"
  | "nombre_ordinal"
  | "reference_croisee"
  | "choix"
  // AJOUT 24/09/2026 — jamais saisies par l'utilisateur, résolues côté
  // backend depuis ProjectLegalProfile/project_associates (voir
  // _resoudre_variables_auto / _resoudre_variables_associes) et renvoyées
  // déjà résolues dans ClauseCandidateRead.valeurs_auto_resolues.
  | "auto_forme_juridique"
  | "auto_nom_societe"
  | "auto_profil_juridique"
  | "auto_siege_social"
  | "auto_repartition_associes"
  | "auto_pourcentage_associes"
  | "auto_poids_participation"
  // AJOUT 25/09/2026 (service 1.1.4 statuts) — mêmes principes que les
  // auto_* ci-dessus, sauf `auto_identite_associe` : résolue automatiquement
  // (comme les autres) SEULEMENT si `selections_requises` ne liste pas
  // plusieurs candidats pour cette variable ; sinon c'est un vrai choix
  // utilisateur (menu déroulant) — voir ClauseCandidateRead.selections_requises
  // et statuts_sas_resolvers._selections_requises côté backend.
  | "auto_identite_associe"
  | "auto_nom_complet_associe"
  | "auto_adresse_associe"
  | "auto_montant_apports_numeraire"
  | "auto_montant_apports_nature"
  // Pas un auto_* : jamais résolues seules, TOUJOURS une saisie utilisateur,
  // mais répétée une fois par associé concerné (liste dans
  // `selections_requises[nom]`) plutôt qu'une seule fois pour la clause —
  // ex. Article 6 `designation_bien_apporte` (texte) par apporteur en
  // nature, Article 6.2 bis `nombre_actions` (nombre) par apporteur en
  // industrie.
  | "texte_par_associe"
  | "nombre_par_associe"

/** Reflète une entrée de `contract_clauses_library.variables_requises` (JSONB).
 * `options` n'est présent que pour `type: "choix"`. `reference_croisee` n'est
 * JAMAIS affichée à l'utilisateur — résolue côté backend depuis une autre
 * section (voir document_generation_service.py) — le composant de formulaire
 * doit la filtrer avant de rendre les champs. */
export interface ClauseVariable {
  nom: string
  type: VariableType
  libelle: string
  options?: string[]
}

/** Reflète `ClauseCandidateRead` côté backend. `sous_candidats` : rempli
 * seulement si cette clause a un second niveau de choix imbriqué (cas
 * Article 3 uniquement — voir ContractClauseLibrary côté backend). Quand
 * présent, la clause réellement appliquée est la sous-variante choisie, pas
 * celle-ci. */
export interface ClauseCandidateRead {
  code_clause: string
  titre_clause: string
  description_clause: string
  texte_clause: string
  variables_requises: ClauseVariable[]
  /** Valeur déjà résolue des variables de type `auto_*` de cette clause (clé
   * = `variable.nom`) — le champ correspondant se rend en lecture seule
   * plutôt qu'en input éditable. Absente (ou "(non renseigné)") si la donnée
   * source manque côté projet — non bloquant, voir PacteVariableInputV2. */
  valeurs_auto_resolues: Record<string, string>
  /** Pour chaque variable résolue PAR ASSOCIÉ (clé = `variable.nom`), la
   * liste `{id, libelle}` des associés concernés — 2 cas distincts partagent
   * cette même structure (voir la docstring de `_selections_requises` côté
   * backend) :
   * - `auto_identite_associe` : un vrai choix (menu déroulant) — présente
   *   seulement si plusieurs candidats (1 seul => résolu automatiquement,
   *   déjà dans `valeurs_auto_resolues`, jamais ici).
   * - `texte_par_associe`/`nombre_par_associe` : pas un choix — un champ par
   *   associé listé, à soumettre comme `{ [id]: valeur }` dans
   *   `SectionAnswerSubmit.valeurs[nom]` (voir ce type plus bas).
   * Absente (objet vide) pour une clause sans variable de ce type. AJOUTÉ
   * 25/09/2026 : champ déjà calculé côté service depuis le 23/09/2026 mais
   * jusque-là absent du schéma Pydantic de réponse, donc jeté en silence à
   * la sérialisation — voir le correctif dans document_generation_schemas.py. */
  selections_requises: Record<string, { id: string; libelle: string }[]>
  sous_candidats: ClauseCandidateRead[] | null
}

/** Reflète `SectionStateRead` côté backend — état de la section courante
 * (GET .../document-generation/{document_type}). `section_courante === null`
 * avec `statut === "complete"` signale la fin de la collecte (Étape 5). */
/** Article facultatif proposé sur l'écran de choix (statuts, audit #19). */
export interface FacultatifRead {
  code: string
  titre: string
  articles: string[]
  explication: string
  /** Pré-rempli avec le choix précédent si l'utilisateur revient sur l'écran. */
  choisi: boolean
}

export interface SectionStateRead {
  session_id: string
  statut: "en_cours" | "complete"
  code_section: string | null
  comportement_section: SectionComportement | null
  obligatoire: boolean | null
  titre_section: string | null
  explication_section: string | null
  /** Nom de l'article contenant la section (ex. "Article 2 - Cessions libres
   * et Cessions interdites..."), distinct de `titre_section` (la clause elle-
   * même) — 24/09/2026. `null` si non résolu (squelette sans convention de
   * nommage "titre_article_*", voir _nom_article_courant côté backend). */
  nom_article: string | null
  /** Position (1-based) et total estimé de sections interactives, pour la
   * barre de progression — voir _section_progress côté backend, `total`
   * n'est qu'une estimation qui peut légèrement baisser en cours de route. */
  position: number | null
  total_sections_estime: number
  /** Rempli seulement par goToPreviousSection() — réponse précédente de la
   * section restaurée, à utiliser pour préremplir le formulaire. */
  reponse_precedente: Record<string, unknown> | null
  /** Significatif seulement quand statut === "complete" && code_section ===
   * null : true = un document a déjà été généré pour cette session lors
   * d'une visite précédente (finalize() échouerait, voir SessionAlreadyCompleteError
   * côté backend) — le frontend doit alors proposer restartDocumentGeneration()
   * plutôt que réafficher "Finaliser le pacte". */
  document_deja_genere: boolean
  /** Correction d'une section lancée depuis la vérification finale (statuts). */
  correction_en_cours?: boolean
  /** Statuts (audit #19) : pause avant l'Art. 8 sur l'écran de choix des
   * articles facultatifs — `facultatifs` donne la liste à cocher. */
  choix_facultatifs_requis?: boolean
  facultatifs?: FacultatifRead[] | null
  /** Statuts : la section appartient à un article facultatif coché — badge +
   * bouton "Ne plus inclure cet article". */
  article_facultatif_choisi?: boolean
  /** Statuts : section de base de cet article — incluse d'office, pas de
   * question oui/non (ses options internes restent posées). */
  section_de_base_facultatif?: boolean
  clause: ClauseCandidateRead | null
  candidats: ClauseCandidateRead[] | null
}

export interface DocumentGenerationSessionRead {
  id: string
  project_id: string
  document_type: string
  statut: "en_cours" | "complete"
  section_courante: string | null
  document_genere_id: string | null
  created_at: string
  updated_at: string
}

export interface GeneratedDocumentRead {
  document_id: string
  document_type: string
  secure_url: string
  original_filename: string
}

// RETIRÉ (27/09/2026, service 1.1.15) : ClauseExplanationRequest/Read,
// SectionAnsweredRead, explainSection() et listAnsweredSections() —
// l'explication de clause vit désormais uniquement dans
// pacteFondateurCopilotApi.ts (widget copilot), voir la décision de
// consolidation dans document_generation_router.py côté backend.

export interface SectionAnswerSubmit {
  inclus?: boolean
  variante?: string
  /** Rempli seulement si la clause `variante` choisie a des `sous_candidats`
   * (cas Article 3 uniquement). */
  sous_variante?: string
  /** Élargi 25/09/2026 (statuts) : la valeur d'une variable est normalement
   * une chaîne, SAUF `texte_par_associe`/`nombre_par_associe`, où c'est un
   * objet `{ [associateId]: valeur }` (une valeur par associé listé dans
   * `ClauseCandidateRead.selections_requises[nom]`) — reflète
   * `SectionAnswerSubmit.valeurs: dict[str, Any]` côté backend, déjà
   * volontairement non typé strictement là-bas pour cette raison. */
  valeurs?: Record<string, string | Record<string, string>>
  /** Statuts (24/09/2026) : l'utilisateur a vu les avertissements des règles
   * de validité et choisit de continuer (jamais pour un blocage). */
  confirmer_avertissements?: boolean
}

/** Corps du 422 renvoyé par le garde-fou légal (voir
 * legal_clause_guardrail_service.GuardrailResult côté backend) — porté par
 * `detail` de la réponse FastAPI, pas par `message` seul comme les autres
 * erreurs métier. `GuardrailError` le distingue d'une `ApiError` générique
 * pour que PacteFondateursPage puisse afficher l'article cité et la
 * reformulation plutôt qu'un simple message d'erreur plat. */
export interface GuardrailBlockedDetail {
  message: string
  article_cite: string | null
  reformulation_proposee: string | null
  /** Statuts (24/09/2026) : TOUS les problèmes de la section — règles
   * vérifiées par code (niveau A) ou contrôle juridique LLM (niveau B).
   * Absent pour le garde-fou du pacte. */
  problemes?: RegleProbleme[]
  /** Vrai si seuls des avertissements sont présents : l'utilisateur peut
   * confirmer et continuer (`confirmer_avertissements`). */
  avertissements_seulement?: boolean
}

export interface RegleProbleme {
  variable: string
  /** Saisie par associé : l'associé concerné (erreur affichée sous sa case). */
  associe_id?: string | null
  libelle: string
  /** Message complet (affiché dans « Détails »). */
  message: string
  /** Une ligne, affichée sous le champ. */
  message_court?: string
  base_legale: string | null
  gravite: "bloquant" | "avertissement"
  /** Niveau B (garde-fou LLM des statuts) : valeur conforme proposée pour
   * ce champ. Absent pour les règles vérifiées par code. */
  reformulation_proposee?: string | null
}

export class GuardrailError extends Error {
  detail: GuardrailBlockedDetail

  constructor(detail: GuardrailBlockedDetail) {
    super(detail.message)
    this.detail = detail
  }
}

/** Génération refusée par la vérification finale (422 de …/finalize) : porte
 * le même résultat que GET …/validation-finale, pour réafficher la liste. */
export class ValidationFinaleBloqueeError extends Error {
  validation: ValidationFinaleRead

  constructor(message: string, validation: ValidationFinaleRead) {
    super(message)
    this.validation = validation
  }
}

function isGuardrailBlockedDetail(detail: unknown): detail is GuardrailBlockedDetail {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "message" in detail &&
    typeof (detail as { message: unknown }).message === "string"
  )
}

async function request<T>(
  accessToken: string,
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  })

  if (!response.ok) {
    let body: { detail?: unknown } = {}
    try {
      body = await response.json()
    } catch {
      // Réponse sans corps JSON exploitable — traitée comme une ApiError plate ci-dessous.
    }

    // 422 du garde-fou légal : `detail` est un objet structuré (message +
    // article_cite + reformulation_proposee), pas une chaîne — voir
    // _run_guardrail_on_free_text côté backend. Toute autre erreur (ProjectError,
    // DocumentGenerationError...) garde le format `detail: string` habituel.
    if (response.status === 422 && isGuardrailBlockedDetail(body.detail)) {
      const detail = body.detail as GuardrailBlockedDetail & { validation?: ValidationFinaleRead }
      if (detail.validation) throw new ValidationFinaleBloqueeError(detail.message, detail.validation)
      throw new GuardrailError(detail)
    }

    const detail = typeof body.detail === "string" ? body.detail : response.statusText
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function getCurrentSection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<SectionStateRead> {
  return request<SectionStateRead>(accessToken, `/projects/${projectId}/document-generation/${documentType}`)
}

/** Pré-validation au démarrage des statuts (24/09/2026) : ce qui manque dans
 * le projet (Informations légales, Équipe & capital, Dirigeants) avant de
 * pouvoir commencer. `page` = où corriger (lien direct). */
export type PrevalidationPage = "informations_legales" | "equipe_capital" | "dirigeants"

export interface PrevalidationProbleme {
  code: string
  message: string
  page: PrevalidationPage
}

export interface PrevalidationRead {
  pret: boolean
  problemes: PrevalidationProbleme[]
}

export function getPrevalidation(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<PrevalidationRead> {
  return request<PrevalidationRead>(accessToken, `/projects/${projectId}/document-generation/${documentType}/prevalidation`)
}

/** Vérification finale avant génération (24/09/2026) — agent
 * agents/document_generation_validation : une étape par tool, dans l'ordre.
 * `cible_type` "section" = section à rouvrir (`cible` = code_section),
 * "page" = page du projet (`cible` = PrevalidationPage). */
export interface ProblemeValidation {
  code: string
  message_court: string
  message: string
  gravite: "bloquant" | "avertissement"
  cible_type: "section" | "page" | null
  cible: string | null
  cible_libelle: string | null
  base_legale: string | null
  reformulation_proposee: string | null
  /** Carte claire (25/09/2026) : quel champ, quelle valeur, quelle correction. */
  champ: string | null
  valeur_actuelle: string | null
  correction_proposee: string | null
  /** Correction certaine : bouton « Appliquer » (sans rouvrir la section). */
  valeur_a_appliquer: { variable: string; valeur: string } | null
}

export interface EtapeValidation {
  tool: string
  libelle: string
  statut: "ok" | "problemes" | "erreur"
  duree_ms: number
  nb_problemes: number
}

export interface ValidationFinaleRead {
  /** Aucun problème bloquant (des avertissements n'empêchent pas de générer). */
  pret: boolean
  etapes: EtapeValidation[]
  problemes: ProblemeValidation[]
}

export function getValidationFinale(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<ValidationFinaleRead> {
  return request<ValidationFinaleRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/validation-finale`,
  )
}

/** « Corriger → » : rouvre une section sans effacer le reste du parcours. */
export function rouvrirSection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
  codeSection: string,
): Promise<SectionStateRead> {
  return request<SectionStateRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/sections/${encodeURIComponent(codeSection)}/rouvrir`,
    { method: "POST" },
  )
}

/** « Appliquer » une correction certaine proposée par la vérification finale. */
export function appliquerCorrection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
  body: { code_section: string; variable: string; valeur: string },
): Promise<void> {
  return request<void>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/validation-finale/appliquer`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

/** « Revenir à la vérification » : annule la correction en cours. */
export function annulerCorrection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<SectionStateRead> {
  return request<SectionStateRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/correction/annuler`,
    { method: "POST" },
  )
}

export function goToPreviousSection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<SectionStateRead> {
  return request<SectionStateRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/back`,
    { method: "POST" },
  )
}

export function restartDocumentGeneration(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<SectionStateRead> {
  return request<SectionStateRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/restart`,
    { method: "POST" },
  )
}

export function submitSection(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
  codeSection: string,
  body: SectionAnswerSubmit,
): Promise<DocumentGenerationSessionRead> {
  return request<DocumentGenerationSessionRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/sections/${codeSection}`,
    { method: "POST", body: JSON.stringify(body) },
  )
}

/** POST .../facultatifs (statuts, audit #19) — enregistre les articles
 * facultatifs cochés sur l'écran de pause et reprend le parcours. */
export function submitFacultatifs(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
  codesChoisis: string[],
): Promise<DocumentGenerationSessionRead> {
  return request<DocumentGenerationSessionRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/facultatifs`,
    { method: "POST", body: JSON.stringify({ codes_choisis: codesChoisis }) },
  )
}

/** POST .../facultatifs/retirer (statuts, audit #19) — bouton "Ne plus
 * inclure cet article" sur la section courante. */
export function retirerFacultatif(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<DocumentGenerationSessionRead> {
  return request<DocumentGenerationSessionRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/facultatifs/retirer`,
    { method: "POST" },
  )
}

export function finalizeDocumentGeneration(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<GeneratedDocumentRead> {
  return request<GeneratedDocumentRead>(
    accessToken,
    `/projects/${projectId}/document-generation/${documentType}/finalize`,
    { method: "POST" },
  )
}

/** GET .../preview (v2 uniquement pour l'instant) : PDF du document tel que
 * généré à date par les réponses déjà enregistrées (jamais persisté, voir
 * `pdf_rendering_service.render_document_as_pdf` / `_assemble_document_blocks`
 * côté backend). Contourne `request<T>` : la réponse est un flux
 * `application/pdf`, pas du JSON — on ne peut pas faire `response.json()`
 * dessus. Erreurs gérées à la main pour rester cohérent avec `ApiError`. */
export async function getDocumentPreview(
  accessToken: string,
  projectId: string,
  documentType: DocumentGenerationDocumentType,
): Promise<Blob> {
  const response = await fetch(
    `${API_BASE_URL}/projects/${projectId}/document-generation/${documentType}/preview`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  )

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === "string") {
        detail = body.detail
      }
    } catch {
      // Pas de corps JSON exploitable (cas attendu pour la plupart des erreurs
      // ici, la route ne renvoyant du JSON qu'en cas d'erreur) — on garde le
      // statusText plutôt que de faire échouer la lecture de l'erreur elle-même.
    }
    throw new ApiError(response.status, detail)
  }

  return await response.blob()
}
