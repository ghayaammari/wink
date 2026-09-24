import { useCallback, useEffect, useState } from "react"
import { useOutletContext } from "react-router-dom"
import LoadingSpinner from "../../shared/components/LoadingSpinner"
import { useAuth } from "../../shared/context/AuthContext"
import {
  AnnoncePrevalidationError,
  generateLegalAnnouncement,
  getHabilitatedJournals,
  getLegalAnnouncement,
  updateLegalAnnouncementText,
  uploadPublicationCertificate,
  validateLegalAnnouncement,
  type JournauxHabilites,
  type LegalAnnouncementState,
} from "../api/legalAnnouncementApi"
import AnnonceProblemesList from "../components/annonceLegale/AnnonceProblemesList"
import AnnonceProgression from "../components/annonceLegale/AnnonceProgression"
import AnnonceRedactionCard from "../components/annonceLegale/AnnonceRedactionCard"
import AttestationDepotCard from "../components/annonceLegale/AttestationDepotCard"
import JournauxRecommandesCard from "../components/annonceLegale/JournauxRecommandesCard"
import type { MyProjectOutletContext } from "./MyProjectLayout"

/**
 * Page « Annonce légale » (service 1.1.5) — rédaction de l'annonce ET
 * recommandation des journaux habilités sur un même écran : l'entrepreneur
 * relit son texte à gauche et voit à droite où le publier.
 *
 * Source de vérité = serveur : après chaque action, l'état est rechargé
 * (les avertissements, ex. « données modifiées depuis les statuts », sont
 * calculés côté backend et changent avec l'annonce).
 */
export default function LegalAnnouncementPage() {
  const { accessToken } = useAuth()
  const { project } = useOutletContext<MyProjectOutletContext>()

  const [etat, setEtat] = useState<LegalAnnouncementState | null>(null)
  const [journaux, setJournaux] = useState<JournauxHabilites | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [journauxError, setJournauxError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const charger = useCallback(async () => {
    if (!accessToken) return
    // Deux appels indépendants : un échec de la liste des journaux ne doit
    // pas empêcher de rédiger l'annonce (et inversement).
    const [resEtat, resJournaux] = await Promise.allSettled([
      getLegalAnnouncement(accessToken, project.id),
      getHabilitatedJournals(accessToken, project.id),
    ])
    if (resEtat.status === "fulfilled") {
      setEtat(resEtat.value)
      setLoadError(null)
    } else {
      setLoadError("Impossible de charger l'annonce légale pour le moment. Rechargez la page.")
    }
    if (resJournaux.status === "fulfilled") {
      setJournaux(resJournaux.value)
      setJournauxError(null)
    } else {
      setJournauxError("La liste des journaux est indisponible pour le moment.")
    }
  }, [accessToken, project.id])

  useEffect(() => {
    charger()
  }, [charger])

  /** Exécute une action, affiche son erreur, puis recharge l'état serveur. */
  async function agir(action: () => Promise<unknown>) {
    setBusy(true)
    setActionError(null)
    try {
      await action()
    } catch (err) {
      if (err instanceof AnnoncePrevalidationError) {
        // Les données ont changé entre l'affichage et le clic : le rechargement
        // ci-dessous affiche la liste à jour des problèmes.
        setActionError(err.message)
      } else {
        setActionError(err instanceof Error ? err.message : "L'action a échoué. Réessayez.")
      }
    } finally {
      await charger()
      setBusy(false)
    }
  }

  if (loadError) return <p className="text-sm text-red-600">{loadError}</p>
  if (etat === null) return <LoadingSpinner />

  const annonce = etat.annonce
  const token = accessToken!

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Annonce légale</h1>
          <p className="mt-1 text-sm text-gray-500">
            Obligatoire avant l'immatriculation : un avis de constitution publié dans un journal habilité du département
            de votre siège.
          </p>
        </div>
        <AnnonceProgression statut={annonce?.statut ?? null} />
      </div>

      {actionError && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{actionError}</p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          {annonce?.statut !== "attestation_deposee" && (
            <>
              <AnnonceProblemesList problemes={etat.problemes} gravite="bloquant" />
              <AnnonceProblemesList problemes={etat.avertissements} gravite="avertissement" />
            </>
          )}

          <AnnonceRedactionCard
            annonce={annonce}
            pretAGenerer={etat.pret_a_generer}
            busy={busy}
            onGenerate={() => agir(() => generateLegalAnnouncement(token, project.id))}
            onSave={(texte) => agir(() => updateLegalAnnouncementText(token, project.id, texte))}
            onValidate={(texteModifie) =>
              agir(async () => {
                if (texteModifie !== null) await updateLegalAnnouncementText(token, project.id, texteModifie)
                await validateLegalAnnouncement(token, project.id)
              })
            }
          />

          {annonce && (
            <AttestationDepotCard
              annonce={annonce}
              journauxSuggeres={journaux?.journaux ?? []}
              busy={busy}
              onSubmit={async (fichier, journal, date) => {
                // Erreur remontée à la carte (affichée sous le formulaire), pas en haut de page.
                setBusy(true)
                try {
                  await uploadPublicationCertificate(token, project.id, fichier, journal, date)
                  await charger()
                } finally {
                  setBusy(false)
                }
              }}
            />
          )}
        </div>

        <div className="lg:sticky lg:top-6 lg:self-start">
          <JournauxRecommandesCard
            journaux={journaux}
            error={journauxError}
            miseEnAvant={annonce?.statut === "valide_utilisateur"}
          />
        </div>
      </div>
    </div>
  )
}
