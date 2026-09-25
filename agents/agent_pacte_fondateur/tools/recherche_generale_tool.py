"""Tool "recherche_generale" du copilot pacte de fondateurs -- couvre le
besoin "questions libres sur le pacte en general" (portee de la bulle
persistante, decision actee 22/09/2026), sans contexte de clause precise.
"""
from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.tools._semantic_search import search_similar_chunks, to_citable_chunks

TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recherche_generale",
        "description": (
            "Recherche dans le corpus juridique du pacte de fondateurs "
            "(articles de loi, jurisprudence, ressources Bpifrance) pour "
            "repondre a une question generale, non liee a une clause "
            "precise (ex: 'c'est quoi une clause leonine ?')."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "La question de l'utilisateur, reformulee si besoin pour la recherche.",
                },
            },
            "required": ["question"],
        },
    },
}


def recherche_generale(db: Session, *, question: str) -> dict:
    chunks = search_similar_chunks(db, query_texte=question, k=5)
    sources = to_citable_chunks(db, chunks)
    if not sources:
        return {"sources": [], "note": "Aucune source pertinente trouvee dans le corpus pacte de fondateurs."}
    return {"sources": sources}
