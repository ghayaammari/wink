"""Table `company_officers` — mandats de dirigeants désignés dans les statuts SAS (art. 39-41, 44).

Décision de conception validée avec l'utilisateur (22/09/2026, voir historique
"avant de valider je veut apartir de" — catégorie B3 de l'inventaire des 210
variables) :

- `project_associates` répond à "qui possède la société et par quoi" (capital,
  `type_apport`) ; `company_officers` répond à "qui la dirige" (mandat Président
  / Directeur Général / membre du comité). Un Président de SAS peut ne pas être
  associé du tout (ex. Charlotte : aucun % de capital, aucun type_apport) —
  c'est légal, et le stocker dans `project_associates` forcerait une ligne fictive
  à `pourcentage_capital = 0` qui mentirait sur la répartition.
- Anti-redondance : `associate_id` (FK → project_associates.id, NULLABLE). Si le
  dirigeant EST déjà un associé (ex. le fonds X à 20 %, ou Carole présidente),
  on ne stocke QUE la FK — zéro duplication. Si le dirigeant n'est pas associé,
  on stocke son identité ici (`type_personne` + champs PM ou identité).
- `type_personne` : 'personne_physique' | 'personne_morale' (mêmes valeurs que
  `project_associates.type_personne`). Les dirigeants personnes physiques des
  art. 39-41 sont des variables `auto_*_associe` dans le clausier (identité tirée
  des associés) ; les personnes morales portent leurs champs PM ici.
- `duree_fonctions` : rattachée au mandat (art. 39-41), ex. "3 ans".
- Seule la table des mandats est référencée par le moteur de génération (Phase 6/7) :
  les 24 variables dirigeants (denomination_sociale_*, forme_juridique_*, ...) du
  clausier se rempliront depuis cette table quand le dirigeant n'est pas associé.
(réalisé par OPENCODE)
"""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class CompanyOfficer(Base):
    __tablename__ = "company_officers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Mandat exercé (art. 39 Président, 40 Directeur Général, 41 membres du comité,
    # 44 mandataire pour les actes de la société en formation / Annexe III clôture).
    # Un même projet peut avoir plusieurs lignes 'membre_comite' (nombre_membres_comite).
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    # Anti-redondance : si le dirigeant est déjà un associé du projet, on stocke la
    # FK seule ; les champs d'identité ci-dessous restent NULL (pas de duplication).
    associate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_associates.id", ondelete="SET NULL"), nullable=True
    )
    type_personne: Mapped[str] = mapped_column(String(30), nullable=False, server_default="personne_physique")
    duree_fonctions: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # AJOUT (migration acb040c7128a, 23/09/2026) -- identité d'un dirigeant
    # PERSONNE PHYSIQUE non associé (ex. Charlotte, présidente sans capital ni
    # type_apport -- l'exemple même qui justifie cette table, voir docstring de
    # classe). Utilisé seulement si type_personne='personne_physique' ET
    # associate_id IS NULL -- sinon l'identité vit dans project_associates
    # (anti-redondance inchangée). `adresse` (ci-dessous) est réutilisée telle
    # quelle pour ce cas, pas dupliquée.
    nom_complet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Champs personne MORALE dirigeante (ex. une holding présidente), utilisés
    # seulement si type_personne='personne_morale' ET associate_id NULL -- sinon
    # l'identité vit dans project_associates (anti-redondance, voir docstring).
    # Mêmes noms que sur project_associates (personne morale associée) -- même
    # convention "même nom, table différente, ne pas confondre en code review".
    denomination_sociale: Mapped[str | None] = mapped_column(String(255), nullable=True)
    forme_juridique: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capital_social: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    siege_social: Mapped[str | None] = mapped_column(Text, nullable=True)
    lieu_immatriculation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True)
    # Personne physique qui représente cette personne morale dirigeante.
    representant_nom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    representant_prenom: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('president', 'directeur_general', 'membre_comite', 'mandataire')",
            name="ck_company_officers_role",
        ),
        CheckConstraint(
            "type_personne IN ('personne_physique', 'personne_morale')",
            name="ck_company_officers_type_personne",
        ),
    )