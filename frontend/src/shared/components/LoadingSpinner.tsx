interface LoadingSpinnerProps {
  /** Diamètre du cercle en pixels. */
  size?: number
  /** Texte optionnel affiché sous le cercle — absent par défaut, le cercle
   * seul suffit visuellement (voir `sr-only` ci-dessous pour les lecteurs
   * d'écran, qui eux en ont besoin même quand `label` n'est pas fourni). */
  label?: string
}

/**
 * Cercle de chargement partagé — remplace le texte "Chargement..." utilisé
 * jusqu'ici en dur dans chaque page (MyProjectLayout, ProjectLegalInfoPage,
 * ProjectPublicProfilePage, PlanActionPage...). Un seul composant à faire
 * évoluer si le style de chargement change, plutôt que N copies du même
 * `<p>` — voir Wink_architecture_fichiers.md, `shared/` pour ce qui est
 * commun aux 3 acteurs (pas propre à l'entrepreneur malgré son usage actuel).
 *
 * Centré par défaut (`py-10` pour respirer dans son conteneur) : pensé comme
 * remplacement direct du `<p>Chargement...</p>` qui occupait toute la zone de
 * contenu le temps d'un fetch, pas comme un spinner inline à côté d'un bouton
 * (pas ce besoin dans le code actuel — à ajouter avec une prop dédiée le jour
 * où il se présente, plutôt que de le deviner maintenant).
 */
export default function LoadingSpinner({ size = 32, label }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10" role="status" aria-live="polite">
      <div
        className="animate-spin rounded-full border-2 border-gray-200 border-t-indigo-600"
        style={{ width: size, height: size }}
      />
      {label && <p className="text-sm text-gray-500">{label}</p>}
      <span className="sr-only">Chargement en cours</span>
    </div>
  )
}
