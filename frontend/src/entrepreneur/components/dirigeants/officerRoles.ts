import type { CompanyOfficerRead, ProjectAssociateRead, RoleDirigeant } from "../../api/projectApi"

/**
 * Référentiel des rôles de la page Dirigeants (service 1.1.4, lot 5) —
 * partagé par le bloc, la ligne et la fenêtre d'édition, pour que titre,
 * aide et règles (unique / obligatoire / durée) ne soient écrits qu'une fois.
 * `multiple: false` reflète la règle backend (company_officer_service :
 * un seul Président, DG, mandataire).
 */
export interface RoleConfig {
  role: RoleDirigeant
  titre: string
  /** Libellé du bouton d'ajout. */
  ajouter: string
  aide: string
  obligatoire: boolean
  multiple: boolean
  avecDuree: boolean
}

export const ROLES_DIRIGEANTS: RoleConfig[] = [
  {
    role: "president",
    titre: "Président",
    ajouter: "Désigner le Président",
    aide: "Représente la société. Obligatoire dans vos statuts (article 39).",
    obligatoire: true,
    multiple: false,
    avecDuree: true,
  },
  {
    role: "directeur_general",
    titre: "Directeur Général",
    ajouter: "Ajouter un Directeur Général",
    aide: "Seulement si vous cochez l'article « Directeur(s) Général(aux) » dans les statuts (article 40).",
    obligatoire: false,
    multiple: false,
    avecDuree: true,
  },
  {
    role: "membre_comite",
    titre: "Comité de Direction",
    ajouter: "Ajouter un membre",
    aide: "Seulement si vous cochez l'article « Comité de Direction » dans les statuts (article 41).",
    obligatoire: false,
    multiple: true,
    avecDuree: true,
  },
  {
    role: "mandataire",
    titre: "Mandataire pour les actes avant immatriculation",
    ajouter: "Désigner le mandataire",
    aide: "La personne qui signera les actes de la société avant son immatriculation (article 44 et annexe III).",
    obligatoire: false,
    multiple: false,
    avecDuree: false,
  },
]

export function configDuRole(role: RoleDirigeant): RoleConfig {
  return ROLES_DIRIGEANTS.find((r) => r.role === role) ?? ROLES_DIRIGEANTS[0]
}

/** Nom affiché d'un dirigeant : celui de l'associé s'il en est un (source de
 * vérité, jamais dupliquée), sinon son identité propre. */
export function nomDirigeant(o: CompanyOfficerRead, associes: ProjectAssociateRead[]): string {
  if (o.associate_id) {
    return associes.find((a) => a.id === o.associate_id)?.nom_complet ?? "(associé introuvable)"
  }
  const nom = o.type_personne === "personne_morale" ? o.denomination_sociale : o.nom_complet
  return nom || "(nom non renseigné)"
}
