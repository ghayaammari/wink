"""add secteur_fintech / secteur_healthtech domaines on content_embeddings

Revision ID: h5c7d9e1f3a5
Revises: g4b6c8d0e2f4
Create Date: 2026-09-19 00:00:00.000000

Service 3.3.6 (diagnostic d'écart, volet sectoriel HealthTech + FinTech du
service 3.3.5) — même démarche que d3a9f21c6b48 ('rgpd'), a7b3c8d1e4f2
('assurance_sectorielle') et e2c4a6b8d0f1 ('ai_act') : content_embeddings.domaine
est verrouillée par une CheckConstraint (vérifiée au moment de l'embedding, voir
chunk_and_embed_legal_texts.py), on y ajoute les 2 nouveaux domaines en une
seule migration puisque les 2 secteurs sont collectés ensemble (pas de raison
d'ouvrir 2 migrations séparées pour un même service).

legal_texts n'a besoin d'aucune migration ici : domaine_reglementaire est une
colonne String libre, sans CheckConstraint (voir legal_texts.py) — déjà
utilisée telle quelle par blocs_secteur_fintech.py avec la valeur
'secteur_fintech', suffisamment générique pour ne pas nécessiter de mapping
via une fonction type `_domaine_embedding()` (contrairement au cas assurance,
où 11 domaines fins devaient être ramenés à 1 seul domaine content_embeddings).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h5c7d9e1f3a5'
down_revision: Union[str, Sequence[str], None] = 'g4b6c8d0e2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd', 'ai_act', 'secteur_fintech', 'secteur_healthtech')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_content_embeddings_domaine', 'content_embeddings', type_='check')
    op.create_check_constraint(
        'ck_content_embeddings_domaine',
        'content_embeddings',
        "domaine IN ('dbe', 'annonce_legale', 'statuts', 'pre_depot', 'rejet', "
        "'tarifs', 'pacte_fondateurs', 'roadmap', 'forme_juridique', 'statuts_societe', "
        "'assurance_sectorielle', 'rgpd', 'ai_act')",
    )
