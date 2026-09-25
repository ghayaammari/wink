"""Rendu des clauses des statuts SAS (service 1.1.4) -- voir
`document_renderer_base.py` pour le pourquoi de ce découpage (patron
Template Method partagé avec `pacte_fondateurs_renderer.py`).

CORRECTIF (23/09/2026) : le clausier statuts SAS (`statuts_sas_clauses.json`)
écrit ses placeholders avec le NOM technique de la variable (ex.
"(capital_social)", "(activites_societe)", "(objectifs_ess)"), PAS son
libellé -- décision documentée dans `generate_statuts_sas_v2.py::
valider_article()` ("le texte porte `(nom)` de variable... pas le
`libelle`"), déjà respectée par le générateur/validateur du clausier mais
jamais répercutée dans le moteur de rendu, qui utilisait partout `libelle`
(hérité du pacte). Conséquence avant ce correctif : 174 des 176 variables du
clausier statuts ne matchaient jamais leur placeholder -- la valeur saisie
ou auto-résolue restait invisible, le texte brut Bpifrance/statuts
s'affichait tel quel dans le document généré.
"""
from backend.entrepreneur.services.document_renderer_base import ClauseRendererBase

# Valeur RÉELLE du `document_type` des statuts en base (CHECK
# `ck_documents_document_type`, `seed_statuts_sas._DOCUMENT_TYPE`, frontend
# `StatutsSasPage.DOCUMENT_TYPE`). CORRECTIF (24/09/2026) : le moteur testait
# `== "statuts_sas"` en dur à 2 endroits -- valeur qui n'existe nulle part en
# base, donc ces branches n'étaient JAMAIS prises : les statuts étaient
# rendus avec le renderer du pacte (clé `libelle`), ce qui annulait en
# pratique le correctif du 23/09/2026 ci-dessous. Constante unique pour ne
# plus jamais dupliquer la chaîne en dur.
DOCUMENT_TYPE_STATUTS = "statuts"


class StatutsClauseRenderer(ClauseRendererBase):
    def _placeholder_key(self, var: dict) -> str:
        return var["nom"]


statuts_clause_renderer = StatutsClauseRenderer()
