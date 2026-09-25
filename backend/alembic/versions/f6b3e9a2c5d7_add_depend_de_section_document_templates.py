"""add document_templates.depend_de_section / depend_de_variantes

Service 1.1.13 (pacte de fondateurs), Article 3 — en relisant les paragraphes
69-199 du modèle Bpifrance avec l'utilisateur, l'Hypothèse 1 (Fondateurs 1er
rang -> Investisseurs 2e rang) et l'Hypothèse 2 (son miroir) se sont révélées
porter chacune DEUX choix totalité/partiel indépendants (un pour le "1er
rang", un pour le "2nd rang"), alors que `contract_clauses_library.
sous_variantes_candidates` (migration b7e2f4a9c1d6) ne peut exprimer qu'UN
seul niveau de sous-choix par clause candidate. L'Hypothèse 7 (droits de
préférence croisés, para 196) a par ailleurs un choix totalité/partiel du
même genre, entièrement absent du schéma initial.

Décision de conception (actée avec l'utilisateur, 20/09/2026) : plutôt que de
généraliser `sous_variantes_candidates` vers une structure à plusieurs choix
imbriqués par clause (plus complexe, et un seul autre cas — 1.1.4/statuts
n'a pas encore montré de besoin similaire), on découpe "1er rang" et "2nd
rang" en sections `document_templates` SÉPARÉES, chacune une
`variante_obligatoire` normale à 2 candidats (totalité/partiel) — Hypothèse 3
et Hypothèse 7 gardent le mécanisme existant à un niveau, inchangé (Hyp7 a
juste besoin de sa donnée, pas d'un changement de schéma).

Ces sections "1er rang"/"2nd rang" ne doivent apparaître QUE si la bonne
hypothèse a été choisie à la section Article 3 de premier niveau — d'où ce
3e critère d'applicabilité, réutilisant `_applicable()` (déjà étendu une
fois pour `necessite_investisseurs`, migration d3a7c5e8f1b4) plutôt que
d'ajouter un mécanisme de saut de section séparé :
- `depend_de_section` : `code_section` d'une AUTRE section du même
  `document_type`, dont la variante choisie conditionne celle-ci. DOIT
  apparaître plus tôt dans l'ordre (`document_templates.ordre`) — non
  garanti par une contrainte DB (même limite que `reference_type`/
  `reference_id`, cohérence assurée par les données de seed, pas par un
  CHECK inter-lignes).
- `depend_de_variantes` : liste de `contract_clauses_library.code_clause`
  candidats de la section `depend_de_section` — cette section-ci n'est
  applicable QUE si la variante réellement choisie là-bas est dans cette
  liste. Liste explicite plutôt qu'un lien conceptuel implicite, même
  raisonnement que `variantes_candidates` (migration f2c9e0a1b3d4) : un
  renommage de `code_clause` plus tard ne casse pas silencieusement le lien.

Cas particulier volontaire : si la section `depend_de_section` a elle-même
été jugée non applicable (`reponses[...] = {"applicable": False}`) ou
exclue par l'utilisateur (`{"inclus": False}`), la réponse enregistrée n'a
pas de clé `code_clause` — `_applicable()` traite alors cette section-ci
comme non applicable aussi (aucune variante choisie ne peut être "dans" la
liste), ce qui est le comportement voulu : la cascade se propage sans code
spécial.

Revision ID: f6b3e9a2c5d7
Revises: d3a7c5e8f1b4
Create Date: 2026-09-20 15:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'f6b3e9a2c5d7'
down_revision: Union[str, Sequence[str], None] = 'd3a7c5e8f1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'document_templates',
        sa.Column('depend_de_section', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'document_templates',
        sa.Column('depend_de_variantes', JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('document_templates', 'depend_de_variantes')
    op.drop_column('document_templates', 'depend_de_section')
