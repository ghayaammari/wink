import type { PageCorrection } from "../../api/legalAnnouncementApi"
import { PAGES_PROJET } from "../statutsSas/StatutsPrevalidationStep"

/**
 * Pages où corriger une donnée signalée par la pré-validation de l'annonce
 * (service 1.1.5). Reprend les 3 pages du projet déjà utilisées par les
 * statuts (source unique : `PAGES_PROJET`) + la page Statuts elle-même.
 * `annonce_legale` = la page courante : pas de lien.
 */
export const PAGES_CORRECTION: { page: PageCorrection; titre: string; lien: string | null }[] = [
  { page: "statuts", titre: "Statuts", lien: "/entrepreneur/mon-projet/statuts" },
  ...PAGES_PROJET,
  { page: "annonce_legale", titre: "Annonce légale", lien: null },
]
