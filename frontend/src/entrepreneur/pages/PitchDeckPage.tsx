import { useEffect, useState } from "react"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import {
  downloadPitchDeckFile,
  generatePitchDeck,
  getPitchDeck,
  getPitchProfile,
  updatePitchProfile,
  type PitchDeckContent,
  type ProjectPitchProfilePatch,
  type ProjectPitchProfileRead,
} from "../api/pitchApi"
import { getMyProject } from "../api/projectApi"

// Champs du formulaire -- meme liste que ProjectPitchProfilePatch, avec leur
// libelle affiche. L'equipe et le nom/pitch en une ligne ne sont PAS
// redemandes ici : relus depuis "Mon projet" / "Equipe & capital" au moment
// de la generation (voir pitch_deck_service.py::_construire_entree_agent).
const CHAMPS_FORMULAIRE: { cle: keyof ProjectPitchProfilePatch; label: string; placeholder: string }[] = [
  { cle: "probleme", label: "Probleme", placeholder: "Quel probleme resout ta startup, pour qui ?" },
  { cle: "solution", label: "Solution", placeholder: "Comment ton produit resout ce probleme ?" },
  { cle: "marche", label: "Marche", placeholder: "Taille du marche, tendances, opportunite..." },
  { cle: "modele_economique", label: "Modele economique", placeholder: "Comment tu generes des revenus ?" },
  { cle: "concurrence", label: "Concurrence", placeholder: "Qui sont tes concurrents, ta difference ?" },
  { cle: "traction", label: "Traction", placeholder: "Chiffres cles, jalons atteints..." },
  { cle: "financements", label: "Financements / situation actuelle", placeholder: "Levees precedentes, revenus actuels..." },
  { cle: "roadmap", label: "Roadmap", placeholder: "Prochaines etapes, 12-18 mois a venir..." },
  { cle: "demande_investissement", label: "Demande d'investissement", placeholder: "Montant recherche, utilisation des fonds..." },
]

function SlideBullets({ title, bullets }: { title: string; bullets: string[] }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600">
        {bullets.map((bullet, i) => (
          <li key={i}>{bullet}</li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Pitch deck (service 6.6.2, EPIC-06/I5) — entree de premier niveau de la
 * sidebar entrepreneur. Formulaire de saisie (project_pitch_profiles) +
 * bouton de generation (agents/pitch_deck_agent/) + apercu textuel du
 * dernier deck genere + telechargement PPTX.
 *
 * Pas de rendu visuel des 11 diapositives ici (le rendu graphique reel vit
 * dans pitch_deck_renderer_service.py, cote backend, pour le fichier PPTX) :
 * un apercu texte suffit pour valider le contenu avant telechargement --
 * reproduire le rendu PPTX en HTML serait un doublon de complexite non
 * demande (voir "reste sobre").
 */
export default function PitchDeckPage() {
  const { accessToken } = useAuth()
  const [projectId, setProjectId] = useState<string | null>(null)
  const [profile, setProfile] = useState<ProjectPitchProfileRead | null>(null)
  const [draft, setDraft] = useState<ProjectPitchProfilePatch>({})
  const [deck, setDeck] = useState<PitchDeckContent | null>(null)
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken || projectId) return
    getMyProject(accessToken)
      .then((project) => setProjectId(project?.id ?? null))
      .catch(() => setError("Impossible de charger ton projet."))
  }, [accessToken, projectId])

  useEffect(() => {
    if (!accessToken || !projectId) return
    getPitchProfile(accessToken, projectId)
      .then((p) => {
        setProfile(p)
        setDraft({})
      })
      .catch(() => setError("Impossible de charger le profil pitch deck."))
    getPitchDeck(accessToken, projectId)
      .then(setDeck)
      .catch(() => setError("Impossible de charger le dernier pitch deck genere."))
  }, [accessToken, projectId])

  function handleChamp(cle: keyof ProjectPitchProfilePatch, value: string) {
    setDraft((current) => ({ ...current, [cle]: value }))
  }

  async function handleSaveProfile() {
    if (!accessToken || !projectId || Object.keys(draft).length === 0) return
    setIsSavingProfile(true)
    setError(null)
    try {
      const updated = await updatePitchProfile(accessToken, projectId, draft)
      setProfile(updated)
      setDraft({})
    } catch {
      setError("Impossible d'enregistrer le formulaire.")
    } finally {
      setIsSavingProfile(false)
    }
  }

  async function handleGenerate() {
    if (!accessToken || !projectId || isGenerating) return
    setIsGenerating(true)
    setError(null)
    try {
      // Le formulaire non enregistre doit d'abord etre sauvegarde : la
      // generation lit project_pitch_profiles en base, pas le brouillon local.
      if (Object.keys(draft).length > 0) {
        await updatePitchProfile(accessToken, projectId, draft)
        setDraft({})
      }
      const content = await generatePitchDeck(accessToken, projectId)
      setDeck(content)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "La generation du pitch deck a echoue, reessaie dans quelques instants."
          : "Une erreur est survenue.",
      )
    } finally {
      setIsGenerating(false)
    }
  }

  async function handleDownload() {
    if (!accessToken || !projectId || isDownloading) return
    setIsDownloading(true)
    setError(null)
    try {
      await downloadPitchDeckFile(accessToken, projectId)
    } catch {
      setError("Le telechargement a echoue, reessaie dans quelques instants.")
    } finally {
      setIsDownloading(false)
    }
  }

  const valeurChamp = (cle: keyof ProjectPitchProfilePatch): string =>
    (draft[cle] ?? profile?.[cle] ?? "") as string

  return (
    <div className="flex flex-col gap-6 pb-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-gray-900">Pitch deck</h1>
        <p className="text-sm text-gray-500">
          Renseigne les grandes lignes de ta startup — le nom, le pitch en une ligne, le logo et l'equipe sont deja
          repris de "Mon projet". Le copilot genere ensuite les 11 diapositives.
        </p>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 md:grid-cols-2">
        {CHAMPS_FORMULAIRE.map(({ cle, label, placeholder }) => (
          <label key={cle} className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-gray-700">{label}</span>
            <textarea
              value={valeurChamp(cle)}
              onChange={(e) => handleChamp(cle, e.target.value)}
              placeholder={placeholder}
              rows={3}
              className="resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
            />
          </label>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleSaveProfile}
          disabled={isSavingProfile || Object.keys(draft).length === 0}
          className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-50"
        >
          {isSavingProfile ? "Enregistrement..." : "Enregistrer le formulaire"}
        </button>
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating || !projectId}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isGenerating ? "Generation..." : deck ? "Regenerer le pitch deck" : "Generer le pitch deck"}
        </button>
        {deck && (
          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50"
          >
            {isDownloading ? "Preparation du fichier..." : "Telecharger en PPTX"}
          </button>
        )}
      </div>

      {deck && (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="text-xs uppercase tracking-wide text-gray-400">Titre</p>
            <h2 className="text-lg font-semibold text-gray-900">{deck.slides.title.startup_name}</h2>
            <p className="text-sm text-gray-600">{deck.slides.title.one_liner}</p>
          </div>
          <SlideBullets title={deck.slides.problem.title} bullets={deck.slides.problem.bullets} />
          <SlideBullets title={deck.slides.solution.title} bullets={deck.slides.solution.bullets} />
          <SlideBullets title={deck.slides.market.title} bullets={deck.slides.market.bullets} />
          <SlideBullets title={deck.slides.business_model.title} bullets={deck.slides.business_model.bullets} />
          <SlideBullets title={deck.slides.competition.title} bullets={deck.slides.competition.bullets} />
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-gray-900">{deck.slides.traction.title}</h3>
            {deck.slides.traction.metrics.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-4">
                {deck.slides.traction.metrics.map((m, i) => (
                  <div key={i} className="text-sm">
                    <span className="font-semibold text-indigo-700">{m.value}</span>{" "}
                    <span className="text-gray-500">{m.label}</span>
                  </div>
                ))}
              </div>
            )}
            {deck.slides.traction.milestones.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm text-gray-600">
                {deck.slides.traction.milestones.map((m, i) => (
                  <li key={i}>
                    <span className="font-medium text-gray-700">{m.date}</span> — {m.label}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-gray-900">{deck.slides.team.title}</h3>
            <ul className="mt-2 space-y-1 text-sm text-gray-600">
              {deck.slides.team.members.map((m, i) => (
                <li key={i}>
                  <span className="font-medium text-gray-700">{m.name}</span> — {m.role}
                </li>
              ))}
            </ul>
          </div>
          <SlideBullets title={deck.slides.financials.title} bullets={deck.slides.financials.bullets} />
          <SlideBullets title={deck.slides.roadmap.title} bullets={deck.slides.roadmap.bullets} />
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-gray-900">{deck.slides.cta.title}</h3>
            <p className="mt-1 text-sm font-medium text-indigo-700">{deck.slides.cta.ask_summary}</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600">
              {deck.slides.cta.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}
