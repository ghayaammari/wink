"""create company_officers table (mandats de dirigeants, statuts SAS art. 39-41)

Service 1.1.4 (statuts SAS) — catégorie B3 de l'inventaire des 210 variables
(voir historique "avant de valider je veut apartir de", 22/09/2026) : les 24
variables dirigeants désignés (art. 39 Président, 40 Directeur Général, 41
membres du comité — denomination_sociale_*, forme_juridique_*, capital_*,
siege_social_*, rcs_*, numero_siren_*, nom_complet_representant_*,
adresse_representant_*) sont persistées dans une table de mandats dédiée.

Décisions de conception actées avec l'utilisateur :
- `project_associates` répond à "qui possède la société et par quoi" (capital,
  type_apport) ; `company_officers` répond à "qui la dirige" (mandat). Un
  Président de SAS peut ne pas être associé — le stocker dans
  `project_associates` imposerait une ligne fictive à pourcentage_capital=0 qui
  fausserait la répartition (CHECK industrie/capital-zero).
- Anti-redondance : `associate_id` (FK → project_associates.id, NULLABLE).
  Si le dirigeant EST déjà un associé, on stocke la FK seule ; les champs
  d'identité copiés ne le sont que dans le cas contraire (dirigeant PM non
  associé, ex. une holding présidente).
- `role` avec CHECK ('president'|'directeur_general'|'membre_comite') ; un même
  projet peut avoir plusieurs lignes 'membre_comite' (nombre_membres_comite) —
  donc pas de contrainte d'unicité sur (project_id, role).
- `type_personne` mêmes valeurs que project_associates ('personne_physique'|
  'personne_morale'). Les dirigeants personnes physiques des art. 39-41 sont des
  variables auto_*_associe dans le clausier (identité tirée des associés) — le
  modèle suppose le dirigeant PP = associé (cohérent avec
  project_legal_profiles.legal_representative_associate_id).
- `duree_fonctions` rattachée au mandat (art. 39-41).
- Champs personne morale dirigeante : mêmes noms que project_associates
  (personne morale associée) — même convention "même nom, table différente,
  ne pas confondre en code review".
(réalisé par OPENCODE)

Revision ID: e4f6a8b2c0d1
Revises: f5a7c9e1d3b2
Create Date: 2026-09-23 11:35:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f6a8b2c0d1'
down_revision: Union[str, Sequence[str], None] = 'f5a7c9e1d3b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'company_officers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('associate_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('project_associates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('type_personne', sa.String(30), nullable=False, server_default='personne_physique'),
        sa.Column('duree_fonctions', sa.String(120), nullable=True),
        sa.Column('denomination_sociale', sa.String(255), nullable=True),
        sa.Column('forme_juridique', sa.String(120), nullable=True),
        sa.Column('capital_social', sa.Numeric(14, 2), nullable=True),
        sa.Column('siege_social', sa.Text(), nullable=True),
        sa.Column('lieu_immatriculation', sa.String(120), nullable=True),
        sa.Column('siren', sa.String(9), nullable=True),
        sa.Column('representant_nom', sa.String(120), nullable=True),
        sa.Column('representant_prenom', sa.String(120), nullable=True),
        sa.Column('adresse', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "role IN ('president', 'directeur_general', 'membre_comite')",
            name='ck_company_officers_role',
        ),
        sa.CheckConstraint(
            "type_personne IN ('personne_physique', 'personne_morale')",
            name='ck_company_officers_type_personne',
        ),
    )
    op.create_index('ix_company_officers_project_id', 'company_officers', ['project_id'])
    op.create_index('ix_company_officers_associate_id', 'company_officers', ['associate_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_company_officers_associate_id', table_name='company_officers')
    op.drop_index('ix_company_officers_project_id', table_name='company_officers')
    op.drop_table('company_officers')