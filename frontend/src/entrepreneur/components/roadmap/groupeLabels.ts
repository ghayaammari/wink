/** Libellés lisibles pour les groupes du JSON source (g0..g4) — purement
 * présentationnel, aucune logique métier ici (voir "Plan d'action
 * pré-création : spécification", section 6). Partagé entre la vue accordéon
 * (GroupeNodes) et la vue parcours continu (RoadmapPathView) pour éviter de
 * dupliquer cette table dans les deux fichiers. */
export const GROUPE_LABELS: Record<string, string> = {
  g0_decisions_prealables: "Décisions préalables",
  g1_constitution_capital: "Constitution du capital",
  g2_formalites_prealables: "Formalités préalables",
  g3_immatriculation: "Immatriculation",
  g4_obligations_post: "Obligations post-immatriculation",
}
