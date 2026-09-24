"""Schémas Pydantic pour `project_associates` — liste réelle des associés d'un projet.

Spécification Groupe 5 (service1.1.6 / statuts 1.1.4 / pacte 1.1.13) :
- `pourcentage_droits_vote` NULL = droits proportionnels au capital (1 action = 1 voix) ;
- apport en industrie : capital 0 (CHECK DB, art. 1843-2) mais droits de vote possibles ;
- `linked_user_id` est écrit par le backend (associé = propriétaire du projet),
  jamais reçu du client — absent de ces schémas.
Modèle d'édition "brouillon + PUT global" : les opérations unitaires autorisent des
totaux intermédiaires ; la règle "somme = 100 %" est validée par replace_associates
sur l'état cible complet (voir associate_service.py). (réalisé par OPENCODE)
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectAssociateBase(BaseModel):
    nom_complet: str = Field(min_length=1, max_length=255)
    type_personne: Literal["personne_physique", "personne_morale"] = "personne_physique"
    date_naissance: date | None = None
    lieu_naissance: str | None = Field(default=None, max_length=120)
    nationalite: str | None = Field(default=None, max_length=60)
    adresse: str | None = None
    # AJOUT (migration —, service 1.1.4 statuts) — situation et régime
    # matrimonial des fondateurs, utilisée par le patron personne physique de
    # l'en-tête du clausier SAS. NULLABLE (saisie lors de la génération),
    # pertinent seulement si type_personne='personne_physique'.
    situation_et_regime_matrimonial: str | None = Field(default=None, max_length=255)
    pourcentage_capital: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    pourcentage_droits_vote: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    type_apport: Literal["numeraire", "nature", "industrie"] = "numeraire"
    # AJOUT (lot 2, 24/09/2026, service 1.1.4) — colonne en base depuis la
    # migration d3f7a1c9e5b4 mais jamais exposée : c'est la désignation du bien
    # apporté, lue automatiquement par les statuts (Art. 6.1 et 6.2). Pertinente
    # seulement si type_apport == "nature" (vidée sinon, voir validateur).
    description_apport_nature: str | None = None
    est_dirigeant: bool = False
    fonction_dirigeant: str | None = Field(default=None, max_length=120)
    foyer_fiscal_dirigeant_associate_id: UUID | None = None
    est_partie_au_pacte_fondateurs: bool = False
    # AJOUT (migration c8f4d1a6b2e9, service 1.1.13) — voir docstring de la migration.
    est_fondateur: bool = False
    # AJOUT (migration b2c4d6e8f0a2, service 1.1.13) — infos personne morale.
    # Colonnes présentes en base depuis cette migration mais JAMAIS exposées ici
    # jusqu'à ce correctif (24/09/2026) : le formulaire "Équipe & capital" ne
    # pouvait ni lire ni écrire ces champs, alors même que le rendu du pacte
    # (`_render_patron_associe_v2`) les attend et affiche des placeholders
    # "(non renseigné)" à leur place. Tous nullable, pertinents seulement si
    # `type_personne == "personne_morale"` (pas de CHECK inter-champs, cohérent
    # avec le reste de la table).
    denomination_sociale: str | None = Field(default=None, max_length=255)
    type_societe: str | None = Field(default=None, max_length=60)
    capital_social: Decimal | None = Field(default=None, ge=Decimal("0"))
    siege_social: str | None = None
    lieu_immatriculation: str | None = Field(default=None, max_length=120)
    numero_siren: str | None = Field(default=None, max_length=9)
    representant_nom: str | None = Field(default=None, max_length=120)
    representant_prenom: str | None = Field(default=None, max_length=120)
    representant_qualite: str | None = Field(default=None, max_length=120)

    @field_validator("pourcentage_capital", "pourcentage_droits_vote")
    @classmethod
    def _deux_decimales(cls, v):
        # Décimal : 0,01 à 100,00 — pas besoin de plus de 2 décimales pour des parts.
        if v is not None and v.as_tuple().exponent < -2:
            raise ValueError("2 décimales maximum")
        return v

    @model_validator(mode="after")
    def _industrie_capital_zero(self):
        # Même règle que le CHECK en base — retour d'erreur 422 propre avant la DB.
        if self.type_apport == "industrie" and self.pourcentage_capital != 0:
            raise ValueError("un apport en industrie ne concourt jamais au capital (art. 1843-2)")
        # Une désignation d'apport en nature n'a pas de sens pour un autre type
        # d'apport : vidée plutôt que refusée (l'utilisateur a pu changer le type
        # après l'avoir saisie) -- évite qu'une ancienne valeur ressorte un jour.
        if self.type_apport != "nature":
            self.description_apport_nature = None
        if self.est_dirigeant and not self.fonction_dirigeant:
            raise ValueError("un dirigeant doit avoir une fonction renseignée")
        return self


class ProjectAssociateCreate(ProjectAssociateBase):
    """`project_id` vient du chemin de la route (`/projects/{project_id}/associates`)."""


class ProjectAssociateBatchItem(ProjectAssociateBase):
    """Élément du PUT /projects/{id}/associates — la liste complète envoyée au clic
    "Enregistrer". `id` présent = mise à jour d'une ligne existante, absent = création.
    Reflète l'état cible validé par le service (somme = 100 %, ≥ 1 dirigeant).
    (réalisé par OPENCODE)
    """

    id: UUID | None = None


class ProjectAssociateUpdate(BaseModel):
    """PATCH partiel — le pourcentage courant doit être resoumis avec sa nouvelle valeur
    (règle bloquante "somme = 100 %" appliquée sur l'ensemble)."""

    nom_complet: str | None = Field(default=None, min_length=1, max_length=255)
    type_personne: Literal["personne_physique", "personne_morale"] | None = None
    date_naissance: date | None = None
    lieu_naissance: str | None = Field(default=None, max_length=120)
    nationalite: str | None = Field(default=None, max_length=60)
    adresse: str | None = None
    situation_et_regime_matrimonial: str | None = Field(default=None, max_length=255)
    pourcentage_capital: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    pourcentage_droits_vote: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    type_apport: Literal["numeraire", "nature", "industrie"] | None = None
    description_apport_nature: str | None = None
    est_dirigeant: bool | None = None
    fonction_dirigeant: str | None = Field(default=None, max_length=120)
    foyer_fiscal_dirigeant_associate_id: UUID | None = None
    est_partie_au_pacte_fondateurs: bool | None = None
    est_fondateur: bool | None = None
    denomination_sociale: str | None = Field(default=None, max_length=255)
    type_societe: str | None = Field(default=None, max_length=60)
    capital_social: Decimal | None = Field(default=None, ge=Decimal("0"))
    siege_social: str | None = None
    lieu_immatriculation: str | None = Field(default=None, max_length=120)
    numero_siren: str | None = Field(default=None, max_length=9)
    representant_nom: str | None = Field(default=None, max_length=120)
    representant_prenom: str | None = Field(default=None, max_length=120)
    representant_qualite: str | None = Field(default=None, max_length=120)


class ProjectAssociateRead(ProjectAssociateBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    linked_user_id: UUID | None
    created_at: datetime
    updated_at: datetime