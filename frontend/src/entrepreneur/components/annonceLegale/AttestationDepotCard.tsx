import { useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import type { JournalHabilite, LegalAnnouncementRead } from "../../api/legalAnnouncementApi"

interface Props {
  annonce: LegalAnnouncementRead
  journauxSuggeres: JournalHabilite[]
  busy: boolean
  onSubmit: (fichier: File, journal: string, datePublication: string) => Promise<void>
}

// Mêmes limites que le backend (legal_announcement_service.py) : contrôlées
// ici pour un retour immédiat, re-vérifiées côté serveur (seule vraie garantie).
const TAILLE_MAX = 10 * 1024 * 1024
const TYPES_ACCEPTES = ["application/pdf", "image/png", "image/jpeg"]

function aujourdHui(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`
}

function formaterDate(iso: string | null): string {
  if (!iso) return ""
  const [a, m, j] = iso.split("-")
  return `${j}/${m}/${a}`
}

/**
 * Dépôt de l'attestation de parution (service 1.1.5) : dernière étape, faite
 * après la publication hors de Wink. Une fois déposée, l'annonce est
 * verrouillée et l'attestation rangée dans le coffre-fort.
 */
export default function AttestationDepotCard({ annonce, journauxSuggeres, busy, onSubmit }: Props) {
  const [fichier, setFichier] = useState<File | null>(null)
  const [journal, setJournal] = useState("")
  const [datePublication, setDatePublication] = useState("")
  const [erreur, setErreur] = useState<string | null>(null)

  if (annonce.statut === "attestation_deposee") {
    return (
      <section className="flex flex-col gap-2 rounded-lg border border-green-200 bg-green-50 p-5">
        <h2 className="text-sm font-semibold text-green-900">Attestation de parution déposée ✓</h2>
        <p className="text-sm text-green-900">
          Publiée dans <strong>{annonce.journal_utilise}</strong> le {formaterDate(annonce.date_publication)}.
        </p>
        <Link to="/entrepreneur/mon-projet/coffre-fort" className="text-sm font-medium text-green-800 hover:underline">
          Voir l'attestation dans le coffre-fort →
        </Link>
      </section>
    )
  }

  const actif = annonce.statut === "valide_utilisateur"

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setErreur(null)
    if (!fichier) return setErreur("Choisissez le fichier de l'attestation.")
    if (!TYPES_ACCEPTES.includes(fichier.type)) return setErreur("Format non accepté : PDF, PNG ou JPEG.")
    if (fichier.size > TAILLE_MAX) return setErreur("Le fichier dépasse 10 Mo.")
    if (!journal.trim()) return setErreur("Indiquez le journal dans lequel l'annonce a été publiée.")
    if (!datePublication) return setErreur("Indiquez la date de parution.")
    try {
      await onSubmit(fichier, journal.trim(), datePublication)
    } catch (err) {
      setErreur(err instanceof Error ? err.message : "Le dépôt a échoué. Réessayez.")
    }
  }

  return (
    <section
      className={`flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-5 ${actif ? "" : "opacity-60"}`}
    >
      <div>
        <h2 className="text-sm font-semibold text-gray-900">Attestation de parution</h2>
        <p className="mt-1 text-xs text-gray-500">
          {actif
            ? "Une fois l'annonce publiée, déposez l'attestation remise par le journal : elle est exigée pour l'immatriculation."
            : "Disponible après validation du texte de l'annonce."}
        </p>
      </div>

      <form onSubmit={envoyer} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm text-gray-700">
          Fichier (PDF, PNG ou JPEG, 10 Mo max)
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
            disabled={!actif || busy}
            onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Journal de publication
            <input
              type="text"
              list="journaux-annonce-legale"
              value={journal}
              maxLength={255}
              disabled={!actif || busy}
              onChange={(e) => setJournal(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <datalist id="journaux-annonce-legale">
              {journauxSuggeres.map((j) => (
                <option key={j.id} value={j.nom_journal} />
              ))}
            </datalist>
          </label>
          <label className="flex flex-col gap-1 text-sm text-gray-700">
            Date de parution
            <input
              type="date"
              value={datePublication}
              max={aujourdHui()}
              disabled={!actif || busy}
              onChange={(e) => setDatePublication(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
        </div>
        {erreur && <p className="text-sm text-red-600">{erreur}</p>}
        <div>
          <button
            type="submit"
            disabled={!actif || busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? "Envoi..." : "Déposer l'attestation"}
          </button>
        </div>
      </form>
    </section>
  )
}
