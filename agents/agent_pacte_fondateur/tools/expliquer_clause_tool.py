"""Tool "expliquer_clause" du copilot pacte de fondateurs -- couvre le besoin
"expliquer cette clause" (contexte de page, voir discussion architecture
22/09/2026). Une tool = une responsabilite, voir regle #5 des instructions
projet (fichier separe par tool).
"""
from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.tools._semantic_search import search_similar_chunks, to_citable_chunks
from backend.shared.knowledge_base.services.contract_clause_library_service import get_by_code

DOCUMENT_TYPE_PACTE_FONDATEURS = "pacte_fondateurs"  # RECORRIGE (26/09/2026, suite) : "pacte_fondateurs_v2" etait juste le temps de la coexistence v1/v2. Le v1 a ete supprime de la base (nettoyage complet, voir DECISIONS.md/recap) et toutes les lignes "pacte_fondateurs_v2" renommees en "pacte_fondateurs" -- une seule version existe desormais, plus besoin de suffixe.

# Schema JSON expose au LLM (Groq tool-calling) -- voir pacte_fondateur_copilot_agent.py.
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "expliquer_clause",
        "description": (
            "Explique une clause du pacte de fondateurs : son role, ce qu'elle "
            "protege, et cite les sources juridiques pertinentes du corpus "
            "(articles de loi, jurisprudence, ressources Bpifrance). A utiliser "
            "des que l'utilisateur demande d'expliquer une clause precise, "
            "identifiee soit par le contexte de page (clause affichee), soit "
            "nommee explicitement dans la question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code_clause": {
                    "type": "string",
                    "description": "Code technique de la clause (ex: 'inalienabilite_fondateurs_partielle_plafond').",
                },
            },
            "required": ["code_clause"],
        },
    },
}


def expliquer_clause(db: Session, *, code_clause: str) -> dict:
    """Ne devine jamais une clause inexistante : si `code_clause` ne
    correspond a rien dans `contract_clauses_library`, renvoie une erreur
    explicite que le LLM doit relayer telle quelle a l'utilisateur, plutot
    que d'inventer une explication generique."""
    clause = get_by_code(db, document_type=DOCUMENT_TYPE_PACTE_FONDATEURS, code_clause=code_clause)
    if clause is None:
        return {"erreur": f"Clause '{code_clause}' introuvable dans le pacte de fondateurs."}

    chunks = search_similar_chunks(db, query_texte=clause.description_clause, k=3)
    return {
        "titre_clause": clause.titre_clause,
        "description_clause": clause.description_clause,
        "texte_clause": clause.texte_clause,
        "sources": to_citable_chunks(db, chunks),
    }
