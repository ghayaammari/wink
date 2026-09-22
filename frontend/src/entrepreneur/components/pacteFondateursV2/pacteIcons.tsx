/** Icônes SVG partagées du pacte v2 (24/09/2026, demande utilisateur : de
 * "bons icons" plutôt que des caractères ASCII "◀"/"▶"/"−"/"+"). Style
 * outline, viewBox 24, même convention que IconActionButton.tsx (l'icône
 * partagée du reste de l'app) — centralisé ici plutôt que dans ce fichier
 * partagé global : ces tracés sont spécifiques aux écrans pacte v2
 * (PacteSectionFormV2, PacteDocumentPreviewV2), pas encore réutilisés
 * ailleurs — à déplacer vers un module commun si un 3e écran en a besoin. */
export const ICON_CHEVRON_LEFT = "M15.75 19.5 8.25 12l7.5-7.5"
export const ICON_CHEVRON_RIGHT = "m8.25 4.5 7.5 7.5-7.5 7.5"
export const ICON_CHECK = "m4.5 12.75 6 6 9-13.5"
export const ICON_SKIP = "M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
export const ICON_TAG = "M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z M6 6h.008v.008H6V6Z"
export const ICON_DOCUMENT = "M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m5.231 13.481L15 17.25m-1.519-3.398L12 16.5m-9-4.5V21h18v-9m-18 0V4.875C3 3.839 3.84 3 4.875 3h9.75c.32 0 .625.075.9.208M3 12l3.75-3.75M3 12l3.75 3.75"
export const ICON_INFO = "M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9-3.75h.008v.008H12V8.25Z"
export const ICON_MINUS = "M5 12h14"
export const ICON_PLUS = "M12 4.5v15m7.5-7.5h-15"

export function Icon({ path, className = "h-4 w-4" }: { path: string; className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  )
}
