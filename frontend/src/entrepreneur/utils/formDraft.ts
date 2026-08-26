/**
 * Sauvegarde locale (brouillon) d'un formulaire d'écran d'onboarding, dans
 * localStorage — mitige la perte de saisie (retour arrière, rechargement,
 * fermeture d'onglet) maintenant qu'un seul appel backend est fait à la fin de
 * l'écran (voir DECISIONS "confirmation globale"), au lieu d'un appel par
 * champ validé comme avant.
 *
 * Pur, sans dépendance React — utilisé par `hooks/useDraftSync.ts` pour
 * l'écriture debouncée, et directement par chaque écran pour la lecture
 * initiale et l'effacement après soumission réussie.
 */

function draftKey(projectId: string, screen: string): string {
  return `wink:draft:${projectId}:${screen}`
}

export function readDraft<T>(projectId: string, screen: string): T | null {
  try {
    const raw = localStorage.getItem(draftKey(projectId, screen))
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    // localStorage indisponible (navigation privée, quota dépassé...) ou JSON
    // corrompu — on dégrade silencieusement vers "pas de brouillon", jamais une
    // erreur bloquante pour un simple confort d'UX.
    return null
  }
}

export function writeDraft<T>(
  projectId: string,
  screen: string,
  value: T,
): void {
  try {
    localStorage.setItem(draftKey(projectId, screen), JSON.stringify(value))
  } catch {
    // idem — un brouillon perdu n'est jamais bloquant, juste moins de confort.
  }
}

export function clearDraft(projectId: string, screen: string): void {
  try {
    localStorage.removeItem(draftKey(projectId, screen))
  } catch {
    // idem
  }
}
