"""Tool "expliquer_impact_variable" du copilot pacte de fondateurs -- couvre
le besoin "expliquer l'impact de chaque variation d'une variable, avec
exemples concrets" (voir discussion architecture 22/09/2026).
"""
from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.tools._semantic_search import search_similar_chunks, to_citable_chunks
from backend.shared.knowledge_base.services.contract_clause_library_service import get_by_code

DOCUMENT_TYPE_PACTE_FONDATEURS = "pacte_fondateurs"  # RECORRIGE (26/09/2026, suite) : "pacte_fondateurs_v2" etait juste le temps de la coexistence v1/v2. Le v1 a ete supprime de la base (nettoyage complet, voir DECISIONS.md/recap) et toutes les lignes "pacte_fondateurs_v2" renommees en "pacte_fondateurs" -- une seule version existe desormais, plus besoin de suffixe.

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "expliquer_impact_variable",
        "description": (
            "Explique l'impact concret de changer la valeur d'une variable "
            "d'une clause (ex: changer la duree d'une clause de "
            "non-concurrence de 1 an a 3 ans). A utiliser quand l'utilisateur "
            "demande ce que change une valeur, ou compare plusieurs valeurs "
            "possibles pour une meme variable."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code_clause": {
                    "type": "string",
                    "description": "Code technique de la clause concernee.",
                },
                "nom_variable": {
                    "type": "string",
                    "description": "Nom technique de la variable (tel que dans variables_requises de la clause).",
                },
            },
            "required": ["code_clause", "nom_variable"],
        },
    },
}


def expliquer_impact_variable(db: Session, *, code_clause: str, nom_variable: str) -> dict:
    """Ne devine jamais une variable inexistante sur la clause -- erreur
    explicite si `nom_variable` n'est pas dans `clause.variables_requises`,
    plutot que de laisser le LLM halluciner un impact pour une variable qui
    n'existe pas sur cette clause."""
    clause = get_by_code(db, document_type=DOCUMENT_TYPE_PACTE_FONDATEURS, code_clause=code_clause)
    if clause is None:
        return {"erreur": f"Clause '{code_clause}' introuvable dans le pacte de fondateurs."}

    variable = next((v for v in clause.variables_requises if v.get("nom") == nom_variable), None)
    if variable is None:
        noms_connus = [v.get("nom") for v in clause.variables_requises]
        return {
            "erreur": (
                f"Variable '{nom_variable}' introuvable sur la clause '{code_clause}'. "
                f"Variables connues : {noms_connus}."
            )
        }

    # Recherche best-effort : toutes les variables n'ont pas de portee
    # juridique directe (ex: un simple nom propre), mais on ne decide jamais
    # a l'avance lesquelles en ont -- le LLM juge de la pertinence des
    # sources renvoyees, une liste vide etant un resultat valide et honnete.
    chunks = search_similar_chunks(db, query_texte=f"{clause.titre_clause} {nom_variable}", k=3)
    return {
        "titre_clause": clause.titre_clause,
        "description_clause": clause.description_clause,
        "variable": variable,
        "sources": to_citable_chunks(db, chunks),
    }
