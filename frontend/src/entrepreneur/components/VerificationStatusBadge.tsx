/**
 * Badge d'un des 3 statuts de vérification de `project_legal_profiles`
 * (denomination/immatriculation/kbis_verification_status). Composant séparé
 * car réutilisé à 2 endroits : le panneau de résultat après clic sur "Mettre
 * à jour" (UpdateLegalProfileForm.tsx) et l'affichage permanent de la section
 * "Immatriculation" (ProjectLegalInfoPage.tsx) — un seul endroit à modifier
 * si les libellés ou couleurs changent.
 */
interface VerificationStatusBadgeProps {
  status: string
}

const LABELS: Record<string, string> = {
  non_verifie: "Non vérifié",
  verifie: "Vérifié",
  incoherent: "Incohérent",
}

const STYLES: Record<string, string> = {
  non_verifie: "bg-amber-50 text-amber-700",
  verifie: "bg-green-50 text-green-700",
  incoherent: "bg-red-50 text-red-700",
}

export default function VerificationStatusBadge({ status }: VerificationStatusBadgeProps) {
  const style = STYLES[status] ?? "bg-gray-100 text-gray-600"
  const label = LABELS[status] ?? status
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {label}
    </span>
  )
}
