import { Link } from "react-router-dom"
import type { JournalHabilite, JournauxHabilites } from "../../api/legalAnnouncementApi"

interface Props {
  journaux: JournauxHabilites | null
  error: string | null
  /** Met la carte en avant quand le texte est validé (étape « Publier »). */
  miseEnAvant: boolean
}

/**
 * Journaux recommandés (service 1.1.5) : journaux papier et services de
 * presse en ligne (SPEL) habilités dans le département du siège — seulement
 * les lignes relues de `jal_reference`. Le lien Service-Public est TOUJOURS
 * affiché : notre référentiel peut être incomplet pour un département.
 *
 * Pas de classement « meilleur journal » : le tarif est un forfait fixé par
 * arrêté, identique partout — le choix est libre.
 */
function ListeJournaux({ titre, journaux }: { titre: string; journaux: JournalHabilite[] }) {
  if (journaux.length === 0) return null
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{titre}</h3>
      <ul className="flex flex-col divide-y divide-gray-100">
        {journaux.map((j) => (
          <li key={j.id} className="flex items-center justify-between gap-2 py-2 text-sm text-gray-800">
            <span>{j.nom_journal}</span>
            {j.lien_site && (
              <a
                href={j.lien_site}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-xs font-medium text-indigo-600 hover:underline"
              >
                Voir ↗
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function JournauxRecommandesCard({ journaux, error, miseEnAvant }: Props) {
  return (
    <section
      className={`flex flex-col gap-4 rounded-lg border bg-white p-5 ${
        miseEnAvant ? "border-indigo-300 ring-2 ring-indigo-100" : "border-gray-200"
      }`}
    >
      <div>
        <h2 className="text-sm font-semibold text-gray-900">Où publier ?</h2>
        <p className="mt-1 text-xs text-gray-500">
          {journaux?.departement_nom
            ? `Journaux habilités pour ${journaux.departement_nom} (${journaux.departement}), département de votre siège.`
            : "Journaux habilités dans le département de votre siège."}
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {journaux && journaux.departement === null && (
        <p className="text-sm text-gray-700">
          Renseignez le code postal de votre siège pour voir les journaux de votre département.{" "}
          <Link to="/entrepreneur/mon-projet/informations-legales" className="font-medium text-indigo-600 hover:underline">
            Compléter →
          </Link>
        </p>
      )}

      {journaux && journaux.departement !== null && journaux.journaux.length === 0 && (
        <p className="text-sm text-gray-700">
          Notre liste n'est pas encore disponible pour ce département. Utilisez la recherche officielle ci-dessous.
        </p>
      )}

      {journaux && (
        <>
          <ListeJournaux titre="Presse en ligne (SPEL)" journaux={journaux.journaux.filter((j) => j.type_support === "spel")} />
          <ListeJournaux titre="Journaux papier" journaux={journaux.journaux.filter((j) => j.type_support === "papier")} />
        </>
      )}

      <div className="flex flex-col gap-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
        <p>
          Le prix d'une annonce de constitution est un <strong>forfait fixé chaque année par arrêté</strong>, identique
          dans tous les journaux habilités : choisissez librement. Le journal vous remet ensuite une attestation de
          parution, à déposer ici.
        </p>
        {journaux && (
          <a
            href={journaux.lien_recherche_officielle}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-indigo-600 hover:underline"
          >
            Recherche officielle des journaux habilités (Service-Public) ↗
          </a>
        )}
      </div>
    </section>
  )
}
