import { type FormEvent, useState } from "react"
import { useNavigate } from "react-router-dom"
import { ApiError } from "../../shared/api/authApi"
import { useAuth } from "../../shared/context/AuthContext"
import { completeOnboarding, type ExtractionPreference } from "../api/researcherProfileApi"

const EXTRACTION_OPTIONS: { value: ExtractionPreference; label: string }[] = [
  { value: "extraire", label: "Extraire automatiquement depuis HAL / OpenAlex" },
  { value: "deposer", label: "Déposer mes travaux manuellement" },
  { value: "les_deux", label: "Les deux" },
]

/**
 * Onboarding chercheur — étapes 3 à 5 du parcours (préférence d'import,
 * affiliation, ORCID conditionnel), envoyées en un seul appel à la fin
 * (POST /chercheur/onboarding — décision actée : pas de sauvegarde
 * intermédiaire, l'onboarding est court, rien à reprendre à mi-chemin).
 *
 * Pas de sidebar ici volontairement — même logique que OnboardingWizard côté
 * entrepreneur : le profil n'est pas encore complet, pas de dashboard à
 * montrer avant la fin de ce formulaire.
 */
export default function ResearcherOnboardingPage() {
  const { accessToken } = useAuth()
  const navigate = useNavigate()

  const [affiliation, setAffiliation] = useState("")
  const [extractionPreference, setExtractionPreference] = useState<ExtractionPreference | null>(null)
  const [orcidId, setOrcidId] = useState("")
  const [domains, setDomains] = useState<string[]>([])
  const [domainInput, setDomainInput] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const needsOrcid = extractionPreference === "extraire" || extractionPreference === "les_deux"

  function addDomain() {
    const trimmed = domainInput.trim()
    // Évite les doublons silencieux plutôt que d'envoyer 2x la même valeur —
    // le backend gère l'unicité (UniqueConstraint) mais autant ne pas
    // multiplier des allers-retours d'erreur pour une saisie répétée.
    if (trimmed && !domains.includes(trimmed)) {
      setDomains([...domains, trimmed])
    }
    setDomainInput("")
  }

  function removeDomain(domain: string) {
    setDomains(domains.filter((d) => d !== domain))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!accessToken || !extractionPreference) return

    // Même règle que côté backend (MissingOrcidError) — vérifiée aussi ici pour
    // un retour immédiat sans aller-retour réseau inutile.
    if (needsOrcid && !orcidId.trim()) {
      setError("L'identifiant ORCID est requis pour cette option.")
      return
    }

    setError(null)
    setIsSubmitting(true)
    try {
      await completeOnboarding(accessToken, {
        affiliation,
        extraction_preference: extractionPreference,
        orcid_id: needsOrcid ? orcidId : null,
        research_domains: domains,
      })
      navigate("/chercheur")
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Une erreur est survenue.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-4">
      <h1 className="text-2xl font-semibold text-gray-900">Complète ton profil chercheur</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <input
          type="text"
          placeholder="Établissement / affiliation"
          value={affiliation}
          onChange={(e) => setAffiliation(e.target.value)}
          required
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Domaines de recherche (optionnel)</p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ex : Intelligence artificielle"
              value={domainInput}
              onChange={(e) => setDomainInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault() // évite de soumettre le formulaire en entier
                  addDomain()
                }
              }}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={addDomain}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:border-gray-400"
            >
              Ajouter
            </button>
          </div>
          {domains.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {domains.map((domain) => (
                <span
                  key={domain}
                  className="flex items-center gap-1 rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700"
                >
                  {domain}
                  <button
                    type="button"
                    onClick={() => removeDomain(domain)}
                    aria-label={`Retirer ${domain}`}
                    className="text-indigo-400 hover:text-indigo-600"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-gray-700">Comment veux-tu ajouter tes travaux ?</p>
          <div className="flex flex-col gap-2">
            {EXTRACTION_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setExtractionPreference(option.value)}
                className={`rounded-lg border px-3 py-2 text-left text-sm font-medium transition ${
                  extractionPreference === option.value
                    ? "border-indigo-600 bg-indigo-50 text-indigo-700"
                    : "border-gray-300 text-gray-700 hover:border-gray-400"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {needsOrcid && (
          <input
            type="text"
            placeholder="Identifiant ORCID (ex: 0000-0002-1825-0097)"
            value={orcidId}
            onChange={(e) => setOrcidId(e.target.value)}
            required
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={isSubmitting || !extractionPreference}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSubmitting ? "Enregistrement..." : "Terminer"}
        </button>
      </form>
    </div>
  )
}
