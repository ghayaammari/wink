"""Persistance + orchestration du copilot pacte de fondateurs.

DEVIATION ASSUMEE de la regle globale du repo "agents/ = IA, backend/.../
services = DB" (voir DECISIONS.md, document_service.py vs
agents/shared/document_processing/) : ce module fait de la persistance DB
(tables pacte_fondateurs_*) alors qu'il vit sous agents/agent_pacte_fondateur/.
Choix delibere pour l'isolation complete demandee par l'utilisateur
(22/09/2026) -- garder ensemble tout ce qui touche les tables isolees, plutot
que d'eclater la logique entre agents/ (agent seul) et backend/entrepreneur/
services/ (persistance), ce qui aurait quand meme force un aller-retour
agents/ <-> backend/ a chaque appel. Le router HTTP, lui, reste dans
backend/entrepreneur/routes/ (convention standard, decision actee).

Appele par le router (backend/entrepreneur/routes/pacte_fondateur_copilot_router.py),
jamais l'inverse -- meme regle que legal_clause_guardrail_service.

Voir agents/agent_pacte_fondateur/tables/pacte_fondateurs_conversation.py
pour le detail de l'isolation volontaire de tout ce dossier.

AJOUT (27/09/2026, service 1.1.15) : `pousser_explication_section` -- ce
module devient AUSSI le point d'entree de l'explication automatique de
clause, en plus des questions libres. Decision de consolidation : 3
mecanismes d'explication avaient ete construits (icone par titre, historique
dedie, copilot), tous supprimes sauf celui-ci -- un seul point d'entree pour
toute explication IA du pacte, question libre ou automatique. Import
volontaire de `agents.contract_agent.clause_explanation_service` (module
frere, pas de cycle) : deviation mineure supplementaire assumee, coherente
avec celle deja actee ci-dessus.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.agent_pacte_fondateur.pacte_fondateur_copilot_agent import gerer_message
from agents.agent_pacte_fondateur.tools._semantic_search import resolve_citation
from agents.agent_pacte_fondateur.tables.pacte_fondateurs_conversation import PacteFondateursConversation
from agents.agent_pacte_fondateur.tables.pacte_fondateurs_message import PacteFondateursMessage
from agents.agent_pacte_fondateur.tables.pacte_fondateurs_response import PacteFondateursResponse
from agents.agent_pacte_fondateur.tables.pacte_fondateurs_response_source import PacteFondateursResponseSource
from agents.contract_agent.clause_explanation_service import ClauseExplanationError, explain_clause
from backend.entrepreneur.services import document_generation_service
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User

# Nombre d'echanges (question+reponse) rechargeants dans l'historique envoye
# au LLM a chaque nouveau message -- limite simple, pas de strategie de
# resume/troncature intelligente. Simplification assumee : une conversation
# tres longue degradera la qualite (contexte tronque) avant d'exploser le
# nombre de tokens -- a revisiter si des sessions de redaction tres longues
# sont observees en usage reel.
_HISTORIQUE_MAX_ECHANGES = 10


class PacteFondateurCopilotError(Exception):
    """Erreur metier du copilot (projet non trouve/non autorise)."""


def _get_or_create_conversation(db: Session, project_id: UUID) -> PacteFondateursConversation:
    conversation = (
        db.query(PacteFondateursConversation)
        .filter(PacteFondateursConversation.project_id == project_id)
        .first()
    )
    if conversation is not None:
        return conversation

    conversation = PacteFondateursConversation(project_id=project_id)
    db.add(conversation)
    db.flush()
    return conversation


def _charger_historique(db: Session, conversation_id: UUID) -> list[dict]:
    messages = (
        db.query(PacteFondateursMessage)
        .filter(PacteFondateursMessage.conversation_id == conversation_id)
        .order_by(PacteFondateursMessage.created_at.desc())
        .limit(_HISTORIQUE_MAX_ECHANGES)
        .all()
    )
    messages.reverse()  # chronologique, pas le plus recent d'abord

    historique: list[dict] = []
    for message in messages:
        historique.append({"role": "user", "content": message.question})
        reponse = (
            db.query(PacteFondateursResponse)
            .filter(PacteFondateursResponse.message_id == message.id)
            .first()
        )
        if reponse is not None:
            historique.append({"role": "assistant", "content": reponse.reponse})
    return historique


def poser_question(
    db: Session,
    user: User,
    project_id: UUID,
    *,
    question: str,
    code_clause_contexte: str | None,
) -> dict:
    """Point d'entree unique du copilot pour le router. Persiste la question,
    appelle l'agent, persiste la reponse + ses sources, dans UNE seule
    transaction (commit ici, pas dans l'agent ni les tools -- coherent avec
    le reste du repo, ex: legal_texts_service ne commit jamais)."""
    project = get_owned_project(db, user, project_id)  # leve ProjectNotFoundError/ForbiddenError si invalide
    conversation = _get_or_create_conversation(db, project.id)
    historique = _charger_historique(db, conversation.id)

    message = PacteFondateursMessage(
        conversation_id=conversation.id,
        question=question,
        code_clause_contexte=code_clause_contexte,
    )
    db.add(message)
    db.flush()

    resultat = gerer_message(
        db,
        question=question,
        code_clause_contexte=code_clause_contexte,
        historique=historique,
    )

    reponse = PacteFondateursResponse(message_id=message.id, reponse=resultat["reponse"])
    db.add(reponse)
    db.flush()

    for source in resultat["sources"]:
        db.add(PacteFondateursResponseSource(
            response_id=reponse.id,
            source_type=source["source_type"],
            source_id=source["source_id"],
        ))

    conversation.updated_at = reponse.created_at
    db.commit()

    return {
        "reponse": resultat["reponse"],
        "sources": resultat["sources"],
    }


def obtenir_historique(db: Session, user: User, project_id: UUID) -> list[dict]:
    """Renvoie l'historique complet (question + reponse + sources), dans
    l'ordre chronologique -- ajoute apres coup (25/09/2026), gap repere en
    construisant le frontend : la conversation etait deja persistee des le
    depart, mais rien ne l'exposait en lecture alors que l'exigence actee
    est "l'historique se persiste" (donc reaffiche a la reouverture de la
    bulle, pas seulement garde en memoire pendant la session du LLM).

    Separee de `_charger_historique()` : celle-ci renvoie tout, au format
    d'affichage (avec sources + citations), pas les _HISTORIQUE_MAX_ECHANGES
    derniers au format role/content attendu par le LLM.

    Cas limite : aucune conversation encore creee pour ce projet -> liste
    vide, pas une erreur (etat normal avant le premier message).
    """
    project = get_owned_project(db, user, project_id)
    conversation = (
        db.query(PacteFondateursConversation)
        .filter(PacteFondateursConversation.project_id == project.id)
        .first()
    )
    if conversation is None:
        return []

    messages = (
        db.query(PacteFondateursMessage)
        .filter(PacteFondateursMessage.conversation_id == conversation.id)
        .order_by(PacteFondateursMessage.created_at.asc())
        .all()
    )

    echanges: list[dict] = []
    for message in messages:
        reponse = (
            db.query(PacteFondateursResponse)
            .filter(PacteFondateursResponse.message_id == message.id)
            .first()
        )
        if reponse is None:
            # Question persistee mais sans reponse (l'appel agent a echoue
            # apres l'ecriture du message, voir poser_question) -- on ne
            # l'affiche pas plutot que de montrer une question orpheline.
            continue

        sources = (
            db.query(PacteFondateursResponseSource)
            .filter(PacteFondateursResponseSource.response_id == reponse.id)
            .all()
        )

        echanges.append({
            "question": message.question,
            "code_clause_contexte": message.code_clause_contexte,
            "reponse": reponse.reponse,
            "sources": [
                {
                    "source_type": s.source_type,
                    "source_id": s.source_id,
                    "citation": resolve_citation(db, source_type=s.source_type, source_id=s.source_id),
                    "chunk_texte": None,  # jamais persiste, voir pacte_fondateurs_response_source.py
                }
                for s in sources
            ],
            "created_at": reponse.created_at.isoformat(),
        })
    return echanges


# ---------------------------------------------------------------------------
# Explication automatique (service 1.1.15)
# ---------------------------------------------------------------------------

_QUESTION_AUTO_EXPLICATION = 'Explique-moi la clause « {titre} ».'


def pousser_explication_section(
    db: Session,
    user: User,
    project_id: UUID,
    *,
    document_type: str,
    code_section: str,
) -> dict | None:
    """Pousse automatiquement, dans CETTE MÊME conversation persistée, une
    explication de la clause affichée par la section courante du
    questionnaire — service 1.1.15 (27/09/2026, consolidation décidée après
    retour "jury" de l'utilisateur : 3 mécanismes d'explication concurrents
    avaient été construits successivement (icône par titre, historique
    dédié, copilot) ; un seul reste, celui-ci, le copilot, qui existait déjà
    et couvrait déjà le besoin conversationnel).

    Utilise `clause_explanation_service.explain_clause` (UN appel LLM dédié)
    et NON `gerer_message`/le RAG de l'agent copilot : ceci n'est pas une
    question de l'utilisateur, c'est une explication automatique déclenchée
    à l'affichage de la section — pas besoin d'une recherche sémantique dans
    la base de connaissances pour ça (voir la distinction déjà actée dans la
    docstring de clause_explanation_service.py). L'utilisateur garde la
    possibilité de reposer une question plus riche (avec citations légales)
    via la suggestion "Explique-moi cette clause" du widget, qui elle passe
    par `poser_question`/le RAG.

    Renvoie `None` sans rien écrire si la section n'a pas de clause unique à
    expliquer (variante_obligatoire sans variante choisie, texte_statique,
    donnee_projet) — mêmes cas que `resolve_target_clause`.

    Idempotent PAR CLAUSE (pas par appel) : si cette clause a déjà été
    expliquée automatiquement dans cette conversation (l'utilisateur revient
    dessus via "Précédent", ou la page se re-rend), l'échange existant est
    renvoyé tel quel plutôt que d'en repousser un doublon dans la
    conversation — l'égalité du texte de la question générée sert de clé
    (aucune colonne dédiée : ne vaut pas une migration pour ce seul besoin,
    dette mineure assumée, un vrai message utilisateur reprenant mot pour
    mot ce texte est un cas limite négligeable).
    """
    project = get_owned_project(db, user, project_id)
    clause = document_generation_service.resolve_target_clause(db, document_type, code_section)
    if clause is None:
        return None

    conversation = _get_or_create_conversation(db, project.id)
    question = _QUESTION_AUTO_EXPLICATION.format(titre=clause.titre_clause)

    existing = (
        db.query(PacteFondateursMessage)
        .filter(
            PacteFondateursMessage.conversation_id == conversation.id,
            PacteFondateursMessage.question == question,
        )
        .first()
    )
    if existing is not None:
        reponse_existante = (
            db.query(PacteFondateursResponse)
            .filter(PacteFondateursResponse.message_id == existing.id)
            .first()
        )
        if reponse_existante is not None:
            return {"question": existing.question, "reponse": reponse_existante.reponse}

    try:
        explication = explain_clause(clause.texte_clause, clause.variables_requises, valeurs=None)
    except ClauseExplanationError as exc:
        raise PacteFondateurCopilotError(f"Explication automatique indisponible : {exc}") from exc

    message = PacteFondateursMessage(
        conversation_id=conversation.id,
        question=question,
        code_clause_contexte=clause.code_clause,
    )
    db.add(message)
    db.flush()

    reponse = PacteFondateursResponse(message_id=message.id, reponse=explication)
    db.add(reponse)
    db.flush()

    conversation.updated_at = reponse.created_at
    db.commit()

    return {"question": question, "reponse": explication}
