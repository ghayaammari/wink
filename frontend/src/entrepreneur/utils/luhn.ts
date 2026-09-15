/**
 * Validation du format d'un SIREN (9 chiffres) par l'algorithme de Luhn —
 * purement locale, aucun appel réseau. Utilisée à l'inscription (Écran 3,
 * Parcours B) pour bloquer un format clairement invalide sans jamais faire
 * dépendre l'inscription d'un service externe.
 *
 * Ne confirme jamais qu'une entreprise existe réellement — juste que le
 * numéro est structurellement valide. La vraie confirmation vient plus tard,
 * au clic sur "Mettre à jour" (voir legal_verification_service.py côté
 * backend, api/projectApi.ts#verifyLegalProfile côté frontend).
 */
export function isValidSirenFormat(siren: string): boolean {
  if (!/^\d{9}$/.test(siren)) return false

  let sum = 0
  for (let i = 0; i < siren.length; i++) {
    let digit = parseInt(siren[siren.length - 1 - i], 10)
    if (i % 2 === 1) {
      digit *= 2
      if (digit > 9) digit -= 9
    }
    sum += digit
  }
  return sum % 10 === 0
}
