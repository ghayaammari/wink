"""
create project_associates table + migrate project_legal_profiles

Services 1.1.13/1.1.4/1.1.6 (Groupe 5 — Incrément 1)

project_associates : table partagée stockant la liste réelle des associés
d'un projet et leur répartition du capital / droits de vote, socle des
services statuts (1.1.4), pacte (1.1.13) et DBE (1.1.6). Contrainte CHECK
"type_apport <> 'industrie' OR pourcentage_capital = 0" (art. 1843-2 CC).
adresse nullable (pas NOT NULL dans le spec) : la ligne du fondateur est
auto-créée à l'accès à la page "Équipe & capital" et ses coordonnées
ne sont pas encore connues à ce stade — à compléter ensuite.
(réalisé par OPENCODE)

project_legal_profiles : le champ legal_representative (JSONB) est supprimé
et remplacé par legal_representative_associate_id (FK → project_associates.id,
nullable — le représentant légal n'est désigné qu'une fois les statuts rédigés,
voir Groupe5_doc.md). Ajout de objet_social / duree_societe /
date_signature_statuts (faits uniques par projet, partagés 1.1.4 → 1.1.5).
(réalisé par OPENCODE)

Revision ID: e1b2c3d4e5f6
Revises: d5e6f7a8b9c1
Create Date: 2026-09-14 22:14:24.294089
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- project_associates (nouvelle — socle partagé Groupe 5) ---  # (réalisé par OPENCODE)
    op.create_table(
        'project_associates',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nom_complet', sa.String(255), nullable=False),
        sa.Column('type_personne', sa.String(30), nullable=False, server_default='personne_physique'),
        sa.Column('date_naissance', sa.Date(), nullable=True),
        sa.Column('lieu_naissance', sa.String(120), nullable=True),
        sa.Column('nationalite', sa.String(60), nullable=True),
        sa.Column('adresse', sa.Text(), nullable=True),
        sa.Column('pourcentage_capital', sa.Numeric(6, 2), nullable=False),
        sa.Column('pourcentage_droits_vote', sa.Numeric(6, 2), nullable=True),
        sa.Column('type_apport', sa.String(20), nullable=False, server_default='numeraire'),
        sa.Column('est_dirigeant', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('fonction_dirigeant', sa.String(120), nullable=True),
        sa.Column('est_partie_au_pacte_fondateurs', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('linked_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "type_personne IN ('personne_physique', 'personne_morale')",
            name='ck_project_associates_type_personne',
        ),
        sa.CheckConstraint(
            "type_apport IN ('numeraire', 'nature', 'industrie')",
            name='ck_project_associates_type_apport',
        ),
        sa.CheckConstraint(
            "type_apport <> 'industrie' OR pourcentage_capital = 0",
            name='ck_project_associates_industrie_capital_zero',
        ),
    )
    op.create_index('ix_project_associates_project_id', 'project_associates', ['project_id'])

    # --- project_legal_profiles : migration + ajout de 4 colonnes ---  # (réalisé par OPENCODE)
    op.drop_column('project_legal_profiles', 'legal_representative')
    op.add_column(
        'project_legal_profiles',
        sa.Column(
            'legal_representative_associate_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('project_associates.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )
    op.add_column('project_legal_profiles', sa.Column('objet_social', sa.Text(), nullable=True))
    op.add_column('project_legal_profiles', sa.Column('duree_societe', sa.Integer(), nullable=True))
    op.add_column(
        'project_legal_profiles',
        sa.Column('date_signature_statuts', sa.Date(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # project_legal_profiles — restauration de legal_representative et suppression des ajouts  # (réalisé par OPENCODE)
    op.drop_column('project_legal_profiles', 'date_signature_statuts')
    op.drop_column('project_legal_profiles', 'duree_societe')
    op.drop_column('project_legal_profiles', 'objet_social')
    op.drop_column('project_legal_profiles', 'legal_representative_associate_id')
    op.add_column(
        'project_legal_profiles',
        sa.Column('legal_representative', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # project_associates  # (réalisé par OPENCODE)
    op.drop_index('ix_project_associates_project_id', table_name='project_associates')
    op.drop_table('project_associates')