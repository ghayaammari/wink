"""Rendu des clauses du pacte de fondateurs (service 1.1.13) -- voir
`document_renderer_base.py` pour le pourquoi de ce découpage (patron
Template Method partagé avec `statuts_sas_renderer.py`).

Le clausier pacte (`pacte_fondateurs_bpifrance_clauses_v2.json`) écrit ses
placeholders avec le LIBELLÉ humain de la variable (ex. "(nombre)",
"(montant du capital social)") -- comportement inchangé par rapport à
l'ancienne fonction libre `_render_clause_texte`, cette classe ne fait que
l'expliciter dans une méthode dédiée plutôt que de le coder en dur dans le
squelette partagé.
"""
from backend.entrepreneur.services.document_renderer_base import ClauseRendererBase


class PacteClauseRenderer(ClauseRendererBase):
    def _placeholder_key(self, var: dict) -> str:
        return var["libelle"]


# Instance unique, réutilisable sans état -- même convention que les modules
# de services de ce repo (pas de singleton Python "magique", juste un objet
# module-level construit une fois).
pacte_clause_renderer = PacteClauseRenderer()
