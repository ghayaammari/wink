"""rename ambiguous columns on contract_clauses_library / document_templates

Service 1.1.13 (Pacte de fondateurs interactif), demandé par l'utilisateur
après relecture du schéma (20/09/2026) — 4 noms jugés peu clairs, sans lien
avec un besoin de conception : ce sont des colonnes déjà en place, ce
correctif ne change ni la structure ni les données, seulement les noms.

- `contract_clauses_library.scenario` -> `code_clause` : c'était une clé
  technique (slug), pas un "scénario" au sens métier — le mot prêtait à
  confusion.
- `contract_clauses_library.scenario_description` -> `description_clause` :
  même remarque, en plus du double usage (matching sémantique ET explication
  affichée au copilot) que le nom ne rendait pas plus clair sous l'un ou
  l'autre nom — gardé volontairement double-usage (voir docstring du modèle),
  seul le nom change ici.
- `document_templates.nom_section` -> `code_section` : c'est une clé
  technique (utilisée dans l'URL de l'API et comme clé du JSON `reponses`),
  jamais affichée à l'utilisateur — "nom" laissait penser le contraire,
  d'où la confusion avec `titre_affiche` (qui, lui, est affiché).
- `document_templates.type_contenu` -> `comportement_section` : ce n'est pas
  un type de contenu (façon MIME) mais ce qui pilote le COMPORTEMENT de la
  section (quelle logique de validation, quel formulaire afficher côté
  frontend) — voir document_generation_service.py.

Renommage pur (`ALTER TABLE ... RENAME COLUMN`) : aucune donnée déplacée,
aucun type changé. Tout le code qui référence ces colonnes (modèles
SQLAlchemy, services, schémas Pydantic, script de seed + JSON source,
frontend TypeScript) est mis à jour dans le même incrément — une colonne
renommée sans son code applicatif casserait silencieusement le service.

Revision ID: d9c4a6b1f3e8
Revises: a3d7e1c8f0b2
Create Date: 2026-09-20 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9c4a6b1f3e8'
down_revision: Union[str, Sequence[str], None] = 'a3d7e1c8f0b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('contract_clauses_library', 'scenario', new_column_name='code_clause')
    op.alter_column('contract_clauses_library', 'scenario_description', new_column_name='description_clause')

    op.alter_column('document_templates', 'nom_section', new_column_name='code_section')
    op.alter_column('document_templates', 'type_contenu', new_column_name='comportement_section')

    # Le CHECK constraint référence le nom de colonne dans son texte SQL —
    # doit être recréé sous le nouveau nom, pas seulement renommé.
    op.drop_constraint('ck_document_templates_type_contenu', 'document_templates', type_='check')
    op.create_check_constraint(
        'ck_document_templates_comportement_section',
        'document_templates',
        "comportement_section IN ('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', "
        "'texte_statique', 'variante_obligatoire')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_document_templates_comportement_section', 'document_templates', type_='check')
    op.create_check_constraint(
        'ck_document_templates_type_contenu',
        'document_templates',
        "type_contenu IN ('mention_obligatoire', 'clause_optionnelle', 'donnee_projet', "
        "'texte_statique', 'variante_obligatoire')",
    )

    op.alter_column('document_templates', 'comportement_section', new_column_name='type_contenu')
    op.alter_column('document_templates', 'code_section', new_column_name='nom_section')

    op.alter_column('contract_clauses_library', 'description_clause', new_column_name='scenario_description')
    op.alter_column('contract_clauses_library', 'code_clause', new_column_name='scenario')
