import type { StatutAnnonce } from "../../api/legalAnnouncementApi"

/**
 * Frise des 4 étapes de l'annonce légale (service 1.1.5). « Publier » se
 * fait hors de Wink : l'étape est considérée en cours dès que le texte est
 * validé, et terminée au dépôt de l'attestation.
 */
const ETAPES = ["Rédiger", "Valider le texte", "Publier dans un journal", "Déposer l'attestation"]

/** Index de l'étape en cours (4 = tout est fait). */
const ETAPE_PAR_STATUT: Record<StatutAnnonce, number> = {
  genere: 1,
  valide_utilisateur: 2,
  attestation_deposee: 4,
}

function etapeCourante(statut: StatutAnnonce | null): number {
  return statut === null ? 0 : ETAPE_PAR_STATUT[statut]
}

export default function AnnonceProgression({ statut }: { statut: StatutAnnonce | null }) {
  const courante = etapeCourante(statut)
  return (
    <ol className="flex flex-wrap gap-2">
      {ETAPES.map((libelle, index) => {
        const faite = index < courante
        const active = index === courante
        return (
          <li
            key={libelle}
            className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${
              faite
                ? "border-green-200 bg-green-50 text-green-700"
                : active
                  ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                  : "border-gray-200 bg-white text-gray-400"
            }`}
          >
            <span>{faite ? "✓" : index + 1}</span>
            {libelle}
          </li>
        )
      })}
    </ol>
  )
}
