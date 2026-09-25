import { useEffect, useState } from "react"
import type { LegalAnnouncementRead } from "../../api/legalAnnouncementApi"

interface Props {
  annonce: LegalAnnouncementRead | null
  pretAGenerer: boolean
  busy: boolean
  onGenerate: () => Promise<void>
  onSave: (texte: string) => Promise<void>
  onValidate: (texteModifie: string | null) => Promise<void>
}

/**
 * Bloc « Rédaction » de l'annonce légale (service 1.1.5).
 *
 * - Pas d'annonce : bouton « Rédiger mon annonce » (désactivé tant que la
 *   pré-validation bloque).
 * - `genere` : texte modifiable (relecture), enregistrer / valider / régénérer.
 * - `valide_utilisateur` : lecture seule + « Modifier » (repasse en relecture,
 *   à revalider — c'est la règle du backend).
 * - `attestation_deposee` : verrouillé (une annonce publiée ne se corrige que
 *   par une annonce rectificative).
 *
 * Régénérer écrase les corrections : confirmation dans la carte (pas de
 * `window.confirm`, qui bloque la page).
 */
export default function AnnonceRedactionCard({ annonce, pretAGenerer, busy, onGenerate, onSave, onValidate }: Props) {
  const [brouillon, setBrouillon] = useState(annonce?.texte_annonce ?? "")
  const [enEdition, setEnEdition] = useState(false)
  const [confirmerRegeneration, setConfirmerRegeneration] = useState(false)
  const [copie, setCopie] = useState(false)

  // Resynchronise le brouillon quand le serveur renvoie un nouveau texte.
  useEffect(() => {
    setBrouillon(annonce?.texte_annonce ?? "")
    setEnEdition(false)
    setConfirmerRegeneration(false)
  }, [annonce?.texte_annonce, annonce?.statut])

  async function copier() {
    if (!annonce) return
    try {
      await navigator.clipboard.writeText(annonce.texte_annonce)
      setCopie(true)
      setTimeout(() => setCopie(false), 2000)
    } catch {
      // Presse-papiers refusé par le navigateur : l'utilisateur peut sélectionner le texte à la main.
    }
  }

  if (annonce === null) {
    return (
      <section className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900">Rédaction de l'annonce</h2>
        <p className="text-sm text-gray-600">
          Wink rédige votre avis de constitution à partir de vos statuts et des informations de votre projet, avec toutes
          les mentions obligatoires (article R210-4 du Code de commerce). Vous le relirez avant de le publier.
        </p>
        <div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={!pretAGenerer || busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {busy ? "Rédaction..." : "Rédiger mon annonce"}
          </button>
        </div>
      </section>
    )
  }

  const modifiable = annonce.statut === "genere" || enEdition
  const verrouillee = annonce.statut === "attestation_deposee"
  const modifie = brouillon.trim() !== annonce.texte_annonce.trim()

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-gray-900">Texte de votre annonce</h2>
        {annonce.statut === "valide_utilisateur" && !enEdition && (
          <span className="rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">Texte validé</span>
        )}
        {verrouillee && (
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">Publiée</span>
        )}
      </div>

      {modifiable ? (
        <>
          <p className="text-xs text-gray-500">
            Relisez chaque ligne. Vous pouvez corriger le texte, par exemple pour résumer l'objet social (il doit être
            « indiqué sommairement »).
          </p>
          <textarea
            value={brouillon}
            onChange={(e) => setBrouillon(e.target.value)}
            rows={14}
            className="w-full rounded-lg border border-gray-300 p-3 font-mono text-sm leading-relaxed text-gray-800 focus:border-indigo-500 focus:outline-none"
          />
        </>
      ) : (
        <pre className="whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50 p-4 font-sans text-sm leading-relaxed text-gray-800">
          {annonce.texte_annonce}
        </pre>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {modifiable && (
          <>
            <button
              type="button"
              onClick={() => onValidate(modifie ? brouillon : null)}
              disabled={busy || !brouillon.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {modifie ? "Enregistrer et valider" : "Valider le texte"}
            </button>
            {modifie && (
              <button
                type="button"
                onClick={() => onSave(brouillon)}
                disabled={busy || !brouillon.trim()}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400 disabled:opacity-50"
              >
                Enregistrer sans valider
              </button>
            )}
            {enEdition && (
              <button
                type="button"
                onClick={() => {
                  setEnEdition(false)
                  setBrouillon(annonce.texte_annonce)
                }}
                className="rounded-lg px-3 py-2 text-sm text-gray-600 hover:text-gray-900"
              >
                Annuler
              </button>
            )}
          </>
        )}

        {annonce.statut === "valide_utilisateur" && !enEdition && (
          <button
            type="button"
            onClick={() => setEnEdition(true)}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
          >
            Modifier
          </button>
        )}

        <button
          type="button"
          onClick={copier}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-400"
        >
          {copie ? "Copié ✓" : "Copier le texte"}
        </button>

        {!verrouillee && !confirmerRegeneration && (
          <button
            type="button"
            onClick={() => setConfirmerRegeneration(true)}
            disabled={busy}
            className="ml-auto rounded-lg px-3 py-2 text-sm text-gray-500 hover:text-gray-800 disabled:opacity-50"
          >
            Régénérer
          </button>
        )}
      </div>

      {confirmerRegeneration && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-900">
          <span>Régénérer remplace le texte actuel et efface vos corrections.</span>
          <button
            type="button"
            onClick={async () => {
              setConfirmerRegeneration(false)
              await onGenerate()
            }}
            disabled={busy}
            className="rounded-lg bg-orange-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-500 disabled:opacity-50"
          >
            Régénérer quand même
          </button>
          <button type="button" onClick={() => setConfirmerRegeneration(false)} className="text-xs underline">
            Annuler
          </button>
        </div>
      )}

      {annonce.statut === "valide_utilisateur" && !enEdition && (
        <p className="text-xs text-gray-500">
          Copiez ce texte et publiez-le dans l'un des journaux habilités de votre département, puis déposez l'attestation
          de parution ci-dessous.
        </p>
      )}
      {enEdition && (
        <p className="text-xs text-gray-500">Après modification, le texte devra être validé à nouveau.</p>
      )}
    </section>
  )
}
