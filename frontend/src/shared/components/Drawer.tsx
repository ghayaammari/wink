import { useEffect, useState, type ReactNode } from "react"

interface DrawerProps {
  title: string
  onClose: () => void
  children: ReactNode
}

/**
 * Panneau qui glisse depuis la droite et reste ancré à droite — fond
 * assombri, fermeture sur clic dehors ou Échap, même mécanique que
 * Modal.tsx (voir ce fichier). Composant séparé plutôt qu'une variante de
 * Modal : la mécanique de positionnement (ancré plein-hauteur à droite,
 * transition de glissement) diffère trop d'un popup centré pour rester
 * lisible derrière une seule prop. Décision comparée dans un artefact
 * (popup centrée vs panneau split vs tiroir) avant implémentation — voir
 * docs/documentation-implementation.md, service 1.1.17.
 *
 * Transition en CSS pure (translate-x, aucune dépendance d'animation
 * Tailwind installée dans ce projet) : monté hors écran puis basculé au
 * prochain repaint via `isOpen`. Pas d'animation de sortie — fermeture
 * immédiate au clic dehors/Échap, comme Modal.tsx n'en a pas non plus ;
 * cohérence plutôt que complexité supplémentaire pour ce premier usage.
 *
 * Premier usage : DocumentPreviewModal.tsx (aperçu de document, 1.1.17).
 * Transverse aux 3 acteurs (pas de logique métier ici), comme Modal.tsx.
 */
export default function Drawer({ title, onClose, children }: DrawerProps) {
  const [isOpen, setIsOpen] = useState(false)

  useEffect(() => {
    const raf = requestAnimationFrame(() => setIsOpen(true))
    return () => cancelAnimationFrame(raf)
  }, [])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose()
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [onClose])

  return (
    <div
      className={`fixed inset-0 z-50 bg-black/40 transition-opacity duration-200 ${isOpen ? "opacity-100" : "opacity-0"}`}
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        className={`absolute inset-y-0 right-0 flex w-full max-w-md flex-col bg-white shadow-xl transition-transform duration-300 ease-out ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-gray-100 p-4">
          <h2 className="truncate text-lg font-semibold text-gray-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="shrink-0 text-gray-400 transition hover:text-gray-600"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  )
}
