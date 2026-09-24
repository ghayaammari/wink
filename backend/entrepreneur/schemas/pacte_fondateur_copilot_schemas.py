"""Schemas Pydantic du copilot pacte de fondateurs (service 1.1.13,
categorie 3) -- expose au frontend via
backend/entrepreneur/routes/pacte_fondateur_copilot_router.py.

Ce fichier suit l'emplacement standard (backend/entrepreneur/schemas/), pas
le dossier isole agents/agent_pacte_fondateur/ -- decision actee avec
l'utilisateur (22/09/2026) : seuls les tables/agent/tools sont isoles pour
eviter une collision avec le travail de la binome, pas la couche HTTP.
"""
from pydantic import BaseModel


class PacteFondateurCopilotQuestion(BaseModel):
    question: str
    code_clause_contexte: str | None = None


class PacteFondateurCopilotSource(BaseModel):
    source_type: str
    source_id: str
    citation: str | None = None
    chunk_texte: str | None = None


class PacteFondateurCopilotReponse(BaseModel):
    reponse: str
    sources: list[PacteFondateurCopilotSource]


class PacteFondateurCopilotHistoryItem(BaseModel):
    """Un echange (question + reponse) de l'historique persiste -- ajoute
    apres coup (24/09/2026) : la conversation etait deja persistee en base
    des le depart (voir pacte_fondateur_copilot_service.py), mais aucune
    route ne l'exposait en lecture -- gap repere en construisant le
    frontend, la bulle devant reafficher l'historique a la reouverture
    (exigence actee : "l'historique se persiste")."""

    question: str
    code_clause_contexte: str | None
    reponse: str
    sources: list[PacteFondateurCopilotSource]
    created_at: str


class PacteFondateurCopilotHistoryRead(BaseModel):
    echanges: list[PacteFondateurCopilotHistoryItem]


class PacteFondateurAutoExplicationRequest(BaseModel):
    """POST .../auto-explication — service 1.1.15 (27/09/2026). Déclenché
    par le frontend à l'affichage d'une nouvelle section du questionnaire,
    pas par une saisie utilisateur — voir
    pacte_fondateur_copilot_service.pousser_explication_section."""

    document_type: str
    code_section: str


class PacteFondateurAutoExplicationRead(BaseModel):
    """Pas de `sources` (contrairement à `PacteFondateurCopilotReponse`) —
    l'explication automatique n'est pas issue d'une recherche RAG, rien à
    citer. `question` est renvoyé pour que le frontend puisse afficher la
    bulle "utilisateur" correspondante sans reformuler le même texte."""

    question: str
    reponse: str
