import { useEffect, useRef } from "react"
import { writeDraft } from "../utils/formDraft"

const DEBOUNCE_MS = 500

/** Persiste `value` dans le brouillon localStorage de cet écran (voir
 * `utils/formDraft.ts`), avec un debounce pour ne pas écrire à chaque frappe.
 * `enabled=false` coupe l'écriture — utilisé pendant la soumission, pour ne
 * pas réécrire un brouillon juste après l'avoir effacé avec `clearDraft`). */
export function useDraftSync<T>(
  projectId: string | undefined,
  screen: string,
  value: T,
  enabled: boolean,
): void {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!enabled || !projectId) return
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      writeDraft(projectId, screen, value)
    }, DEBOUNCE_MS)
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [projectId, screen, value, enabled])
}
