"""migrate project_legal_profiles verification fields (Groupe 4)

Revision ID: 4fa5a487a845
Revises: 03ef7cc7d535
Create Date: 2026-09-12 10:30:00.000000

Retire le statut de vérification unique (`is_registered`/`verification_status`)
au profit de 3 statuts séparés selon l'événement qui les produit — décision
actée dans la page Notion "Schemas grp 4" (Groupe 4 — Services indépendants du
copilot) et reprise dans "Wink — Schémas Incrément 1 v3".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4fa5a487a845'
down_revision: Union[str, Sequence[str], None] = '03ef7cc7d535'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- nouveaux attributs --------------------------------------------------
    op.add_column(
        'project_legal_profiles',
        sa.Column('kbis_document_id', postgresql.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_project_legal_profiles_kbis_document_id',
        'project_legal_profiles', 'documents',
        ['kbis_document_id'], ['id'],
    )
    op.add_column(
        'project_legal_profiles',
        sa.Column('denomination_verification_status', sa.String(length=30), server_default='non_verifie', nullable=False),
    )
    op.add_column(
        'project_legal_profiles',
        sa.Column('immatriculation_verification_status', sa.String(length=30), server_default='non_verifie', nullable=False),
    )
    op.add_column(
        'project_legal_profiles',
        sa.Column('kbis_verification_status', sa.String(length=30), server_default='non_verifie', nullable=False),
    )
    op.add_column(
        'project_legal_profiles',
        sa.Column('numero_suivi_formalite', sa.String(length=100), nullable=True),
    )
    op.create_check_constraint(
        'ck_project_legal_profiles_denomination_verification_status',
        'project_legal_profiles',
        "denomination_verification_status IN ('non_verifie', 'verifie', 'incoherent')",
    )
    op.create_check_constraint(
        'ck_project_legal_profiles_immatriculation_verification_status',
        'project_legal_profiles',
        "immatriculation_verification_status IN ('non_verifie', 'verifie', 'incoherent')",
    )
    op.create_check_constraint(
        'ck_project_legal_profiles_kbis_verification_status',
        'project_legal_profiles',
        "kbis_verification_status IN ('non_verifie', 'verifie', 'incoherent')",
    )

    # --- retrait des anciens attributs ---------------------------------------
    op.drop_column('project_legal_profiles', 'is_registered')
    op.drop_column('project_legal_profiles', 'verification_status')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'project_legal_profiles',
        sa.Column('verification_status', sa.String(length=30), server_default='unverified', nullable=False),
    )
    op.add_column(
        'project_legal_profiles',
        sa.Column('is_registered', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )

    op.drop_constraint('ck_project_legal_profiles_kbis_verification_status', 'project_legal_profiles', type_='check')
    op.drop_constraint('ck_project_legal_profiles_immatriculation_verification_status', 'project_legal_profiles', type_='check')
    op.drop_constraint('ck_project_legal_profiles_denomination_verification_status', 'project_legal_profiles', type_='check')
    op.drop_column('project_legal_profiles', 'numero_suivi_formalite')
    op.drop_column('project_legal_profiles', 'kbis_verification_status')
    op.drop_column('project_legal_profiles', 'immatriculation_verification_status')
    op.drop_column('project_legal_profiles', 'denomination_verification_status')
    op.drop_constraint('fk_project_legal_profiles_kbis_document_id', 'project_legal_profiles', type_='foreignkey')
    op.drop_column('project_legal_profiles', 'kbis_document_id')
