/**
 * Client HTTP pour `backend/entrepreneur/routes/legal_announcement_router.py` —
 * service 1.1.5 (annonce légale de constitution). Même convention que
 * nameAvailabilityApi.ts : accessToken en premier paramètre.
 *
 * Particularité : un refus de génération (422) renvoie `{message, problemes}`
 * dans `detail` — conservé tel quel dans `AnnoncePrevalidationError` pour
 * afficher chaque problème avec son lien « Compléter → », au lieu d'un
 * message aplati.
 */
import { ApiError, parseErrorDetail } from "../../shared/api/authApi"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export type StatutAnnonce = "genere" | "valide_utilisateur" | "attestation_deposee"
/** Pages où corriger une donnée — mêmes codes que la pré-validation des statuts, + statuts/annonce. */
export type PageCorrection = "informations_legales" | "equipe_capital" | "dirigeants" | "statuts" | "annonce_legale"

export interface ProblemeAnnonce {
  code: string
  message: string
  page: PageCorrection
}

export interface LegalAnnouncementRead {
  id: string
  texte_annonce: string
  statut: StatutAnnonce
  date_generation: string
  date_validation_utilisateur: string | null
  journal_utilise: string | null
  date_publication: string | null
  attestation_document_id: string | null
}

export interface LegalAnnouncementState {
  annonce: LegalAnnouncementRead | null
  pret_a_generer: boolean
  problemes: ProblemeAnnonce[]
  avertissements: ProblemeAnnonce[]
  departement: string | null
  departement_nom: string | null
}

export interface JournalHabilite {
  id: string
  nom_journal: string
  type_support: "papier" | "spel"
  lien_site: string | null
}

export interface JournauxHabilites {
  departement: string | null
  departement_nom: string | null
  journaux: JournalHabilite[]
  lien_recherche_officielle: string
}

export class AnnoncePrevalidationError extends ApiError {
  problemes: ProblemeAnnonce[]

  constructor(message: string, problemes: ProblemeAnnonce[]) {
    super(422, message)
    this.problemes = problemes
  }
}

async function request<T>(accessToken: string, path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      // Pas de Content-Type pour un FormData : le navigateur ajoute la frontière multipart lui-même.
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
  })

  if (!response.ok) {
    let detail: unknown = response.statusText
    try {
      detail = (await response.json()).detail ?? detail
    } catch {
      // Réponse sans corps JSON exploitable — on garde statusText.
    }
    if (response.status === 422 && detail && typeof detail === "object" && "problemes" in detail) {
      const d = detail as { message?: string; problemes: ProblemeAnnonce[] }
      throw new AnnoncePrevalidationError(d.message ?? "Informations manquantes.", d.problemes)
    }
    throw new ApiError(response.status, parseErrorDetail(detail, response.statusText))
  }
  return (await response.json()) as T
}

const base = (projectId: string) => `/projects/${projectId}/legal-announcement`

export function getLegalAnnouncement(accessToken: string, projectId: string): Promise<LegalAnnouncementState> {
  return request(accessToken, base(projectId))
}

export function generateLegalAnnouncement(accessToken: string, projectId: string): Promise<LegalAnnouncementRead> {
  return request(accessToken, `${base(projectId)}/generate`, { method: "POST" })
}

export function updateLegalAnnouncementText(
  accessToken: string,
  projectId: string,
  texteAnnonce: string,
): Promise<LegalAnnouncementRead> {
  return request(accessToken, base(projectId), {
    method: "PATCH",
    body: JSON.stringify({ texte_annonce: texteAnnonce }),
  })
}

export function validateLegalAnnouncement(accessToken: string, projectId: string): Promise<LegalAnnouncementRead> {
  return request(accessToken, `${base(projectId)}/validate`, { method: "POST" })
}

export function getHabilitatedJournals(accessToken: string, projectId: string): Promise<JournauxHabilites> {
  return request(accessToken, `${base(projectId)}/journals`)
}

export function uploadPublicationCertificate(
  accessToken: string,
  projectId: string,
  fichier: File,
  journalUtilise: string,
  datePublication: string,
): Promise<LegalAnnouncementRead> {
  const formData = new FormData()
  formData.append("file", fichier)
  formData.append("journal_utilise", journalUtilise)
  formData.append("date_publication", datePublication)
  return request(accessToken, `${base(projectId)}/attestation`, { method: "POST", body: formData })
}
