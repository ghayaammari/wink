/**
 * Déclenche le téléchargement d'un Blob dans le navigateur. Factorisé ici car
 * utilisé à la fois par DocumentVaultPage.tsx (bouton télécharger d'une ligne)
 * et DocumentPreviewModal.tsx (bouton "Télécharger" du repli quand l'aperçu
 * n'est pas disponible) — même logique, pas de raison de la dupliquer.
 *
 * Cloudinary n'est plus référencé directement côté frontend (voir
 * documentVaultApi.ts), donc pas de simple `<a href="...">` possible : on
 * crée une URL d'objet temporaire, on simule le clic sur un lien `download`,
 * puis on la révoque immédiatement pour ne pas garder le Blob en mémoire.
 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
