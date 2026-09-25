"""Table `project_associates` — liste réelle des associés d'un projet et leur
répartition du capital / droits de vote.

Socle partagé des services 1.1.13 (pacte de fondateurs), 1.1.4 (statuts) et
1.1.6 (DBE) — Groupe 5, Incrément 1 (voir Groupe5_doc.md et service1.1.6.md).
Aucune table I0 ne stockait cette liste (projects.nombre_cofondateurs n'est
qu'un entier, project_legal_profiles.legal_representative un seul JSON).

Décisions de conception (voir l'analyse des fichiers de spec) :
- `adresse` est NULLABLE ici (dérivé du spec NOT NULL) : la ligne du fondateur
  est auto-créée dès l'accès à la page "Équipe & capital" (associate_service),
  or `users` ne contient pas encore son adresse — elle est demandée ensuite.
- `linked_user_id` est auto-rempli pour l'associé = propriétaire du projet
  (identité déjà connue depuis I0), quel que soit le nombre de cofondateurs.

Contrainte CHECK : un apport en industrie ne concourt jamais au capital
social (art. 1843-2 du Code civil) — type_apport <> 'industrie' OU
pourcentage_capital = 0.
(réalisé par OPENCODE)
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectAssociate(Base):
    __tablename__ = "project_associates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom_complet: Mapped[str] = mapped_column(String(255), nullable=False)
    type_personne: Mapped[str] = mapped_column(String(30), nullable=False, server_default="personne_physique")
    # Identité — requise pour statuts et DBE quand personne_physique.
    date_naissance: Mapped[date | None] = mapped_column(Date, nullable=True)
    lieu_naissance: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nationalite: Mapped[str | None] = mapped_column(String(60), nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    # AJOUT (migration —, service 1.1.4 statuts) — situation et régime
    # matrimonial des fondateurs (patron personne physique de l'en-tête du
    # clausier SAS, ex. "marié(e) sous le régime de la communauté légale").
    # NULLABLE : renseigné lors de la génération des statuts, sans vérification
    # inter-champs (exigible seulement si type_personne='personne_physique',
    # cohérent avec le reste de la table). Saisie libre (texte), pas d'enum :
    # les régimes matrimoniaux ne forment pas une liste fermée exploitable.
    situation_et_regime_matrimonial: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Répartition : pourcentage_droits_vote NULL = défaut (1 action = 1 voix, égal au capital).
    pourcentage_capital: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    pourcentage_droits_vote: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    type_apport: Mapped[str] = mapped_column(String(20), nullable=False, server_default="numeraire")
    # AJOUT (migration d3f7a1c9e5b4, service 1.1.4 statuts, audit du 23/09/2026,
    # correction #4/ex-P2) -- ce qu'un associé apporte en nature (un bien, pas
    # de l'argent), auparavant piégé dans la session du document statuts
    # (session.reponses["apport_nature_identite"]) et invisible à tout autre
    # service Wink. NULLABLE, pertinente seulement si type_apport='nature' --
    # pas de CHECK inter-champs, même convention que les champs personne
    # morale ci-dessous.
    description_apport_nature: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Repli automatique DBE (si aucun associé ne dépasse 25%) ET population de la
    # condition e21 (droits de vote des dirigeants, régime fiscal) — roadmap_service.
    est_dirigeant: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    fonction_dirigeant: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Foyer fiscal d'un dirigeant (art. 239 bis AB du CGI — condition e21) : NULL =
    # ne fait partie d'aucun foyer fiscal de dirigeant ; sinon id de la ligne de
    # l'associé dirigeant auquel cette personne est rattachée (conjoint/PACS/enfant
    # à charge, art. 6 CGI). La cible doit être est_dirigeant=true (validé service).
    foyer_fiscal_dirigeant_associate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_associates.id", ondelete="SET NULL"), nullable=True
    )
    # AJOUT (migration b2c4d6e8f0a2, service 1.1.13) -- infos propres à une
    # personne morale associée (ex. un fonds d'investissement), manquantes
    # jusqu'ici : seuls des champs personne physique existaient. Tous
    # nullable, utilisés seulement si type_personne='personne_morale' --
    # pas de CHECK inter-champs, cohérent avec le reste de la table.
    denomination_sociale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type_societe: Mapped[str | None] = mapped_column(String(60), nullable=True)
    capital_social: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    siege_social: Mapped[str | None] = mapped_column(Text, nullable=True)
    lieu_immatriculation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    numero_siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    representant_nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    representant_prenom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    representant_qualite: Mapped[str | None] = mapped_column(String(120), nullable=True)
    est_partie_au_pacte_fondateurs: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # AJOUT (migration c8f4d1a6b2e9, service 1.1.13) — distingue Associés
    # Fondateurs / Associés Investisseurs, exigé par le préambule du pacte
    # Bpifrance. Booléen indépendant (pas un enum, pas "est_investisseur" —
    # collision avec users.role) : voir docstring de la migration.
    est_fondateur: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # Auto-rempli avec l'user_id du propriétaire du projet (I0) ; NULL pour les autres.
    linked_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "type_personne IN ('personne_physique', 'personne_morale')",
            name="ck_project_associates_type_personne",
        ),
        CheckConstraint(
            "type_apport IN ('numeraire', 'nature', 'industrie')",
            name="ck_project_associates_type_apport",
        ),
        # Un apport en industrie ne concourt jamais au capital (art. 1843-2 Code civil).
        CheckConstraint(
            "type_apport <> 'industrie' OR pourcentage_capital = 0",
            name="ck_project_associates_industrie_capital_zero",
        ),
    )