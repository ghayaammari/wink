"""add roadmap_nodes.ordre and startup_roadmap_items.proof_document_id

Revision ID: 03ef7cc7d535
Revises: c2e7f4b8a913
Create Date: 2026-09-11 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '03ef7cc7d535'
down_revision: Union[str, Sequence[str], None] = 'c2e7f4b8a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Ordre d'affichage des 24 nœuds — reflète l'ordre du JSON source
# (wink_roadmap_creation_juridique.json), absent du schéma jusqu'ici (oublié
# lors de la construction du Groupe 1). Même rôle que document_templates.ordre
# ailleurs dans le schéma : sans colonne dédiée, l'ordre d'affichage retombe
# sur l'ordre de retour de la requête SQL, jamais garanti. Backfill ponctuel
# ici pour les 24 lignes déjà seedées ; seed_roadmap_nodes.py écrit `ordre`
# pour toute relance future.
_ORDRE_PAR_NODE_ID = [
    ('e1_choix_forme_juridique', 0),
    ('e2_choix_denomination', 1),
    ('e3_verification_disponibilite_nom', 2),
    ('e4_pacte_fondateurs', 3),
    ('e5_redaction_statuts', 4),
    ('e6_domiciliation', 5),
    ('e7a_ouverture_compte_bloque', 6),
    ('e7b_depot_capital', 7),
    ('e8_attestation_depot_fonds', 8),
    ('e9_signature_definitive_statuts', 9),
    ('e9b_annonce_legale', 10),
    ('e10_declaration_non_condamnation', 11),
    ('e11_dbe', 12),
    ('e12_constitution_dossier', 13),
    ('e13_depot_guichet_unique', 14),
    ('e15_verification_immatriculation', 15),
    ('e16_attribution_siren_siret_ape', 16),
    ('e17_obtention_kbis', 17),
    ('e18_deblocage_fonds', 18),
    ('e19_registres_legaux', 19),
    ('e20_affiliation_urssaf', 20),
    ('e21_immatriculation_fiscale', 21),
    ('e22_assurances_obligatoires', 22),
    ('e23_depot_marque', 23),
]


def upgrade() -> None:
    """Upgrade schema."""
    # --- roadmap_nodes.ordre ------------------------------------------------
    # Nullable d'abord : la table a déjà 24 lignes, un NOT NULL direct échouerait.
    op.add_column('roadmap_nodes', sa.Column('ordre', sa.Integer(), nullable=True))

    values_clause = ", ".join(f"('{node_id}', {ordre})" for node_id, ordre in _ORDRE_PAR_NODE_ID)
    op.execute(
        f"""
        UPDATE roadmap_nodes AS rn SET ordre = v.ordre
        FROM (VALUES {values_clause}) AS v(id, ordre)
        WHERE rn.id = v.id
        """
    )
    op.alter_column('roadmap_nodes', 'ordre', nullable=False)

    # --- startup_roadmap_items.proof_document_id ----------------------------
    # Décision actée (voir "Wink — Plan d'action pré-création : spécification",
    # points à trancher) : le lien preuve <-> étape part de startup_roadmap_items
    # vers documents, pas l'inverse — documents reste générique, sans connaître
    # le concept de roadmap.
    op.add_column('startup_roadmap_items', sa.Column('proof_document_id', postgresql.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_startup_roadmap_items_proof_document_id',
        'startup_roadmap_items', 'documents',
        ['proof_document_id'], ['id'],
    )

    # --- startup_roadmap_items.statut : CheckConstraint désormais tranché ---
    # Valeurs actées (voir "Wink — Schémas Incrément 1 v3", section
    # startup_roadmap_items) : verrouille (défaut), a_faire, en_cours, termine,
    # non_necessaire. Absent jusqu'ici volontairement (voir commentaire du
    # modèle avant ce correctif) faute de décision.
    op.create_check_constraint(
        'ck_startup_roadmap_items_statut',
        'startup_roadmap_items',
        "statut IN ('verrouille', 'a_faire', 'en_cours', 'termine', 'non_necessaire')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_startup_roadmap_items_statut', 'startup_roadmap_items', type_='check')
    op.drop_constraint('fk_startup_roadmap_items_proof_document_id', 'startup_roadmap_items', type_='foreignkey')
    op.drop_column('startup_roadmap_items', 'proof_document_id')
    op.drop_column('roadmap_nodes', 'ordre')
