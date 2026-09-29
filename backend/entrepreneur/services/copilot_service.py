"""Logique metier du copilot entrepreneur -- conversations (creer/lister/lire)

et envoi de message dans une conversation. Construit LES 4 jeux de tools
(compliance_agent, administrative_agent, matching_chercheur, matching_offres)
et les passe tous les 4 a l'agent conversationnel (agents/orchestrator/
copilot_agent_service.py) qui route lui-meme vers le bon domaine (voir sa
docstring) -- un seul des 4 jeux sert reellement par appel, mais les
construire tous ici reste bon marche (pas d'appel LLM, juste des fermetures
sur la DB). Puis verification d'ancrage independante avant de persister le
tour complet dans la conversation.

CORRECTIF du 26/09/2026 : les 2 tools de lecture sur le matching (offres
recommandees, chercheurs recommandes) ne sont plus dans le toolset
"conformite" (etat intermediaire du 25/09/2026 v3) -- chacun a maintenant
son propre domaine dans l'orchestrateur ("matching_chercheur",
"matching_offres"), meme pattern de delegation que "reglementaire". Les
tools eux-memes n'ont pas bouge : ils vivent toujours DANS les fichiers de
tools des agents de matching concernes (chercheur_matching_tools_service.py,
startup_offer_matching_tools_service.py), pas dans compliance_agent_tools_
service.py -- respect de l'architecture par domaine (voir Wink_architecture_
fichiers.md), inchange depuis le 25/09/2026 v3. Les 3 agents de CALCUL du
matching (agents/matching_agent/) restent eux completement independants du
copilot -- aucune delegation dans ce sens-la, seuls leurs RESULTATS deja
persistes sont lus ici, jamais un nouveau calcul.

Revient sur la decision V1 "pas de persistance, le frontend renvoie tout
l'historique a chaque appel" -- demande explicite du 20/09/2026 : plusieurs
conversations nommees par projet, listees dans une barre laterale (voir
ProjectCopilotConversation pour le choix JSONB plutot qu'une table
`copilot_messages`).
"""
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from agents.orchestrator.copilot_agent_service import CopilotAgentError, answer_message, verifier_reponse
from agents.shared.groq_runtime.react_agent_runner import ConversationMessage
from backend.entrepreneur.models.project_copilot_conversation import ProjectCopilotConversation
from backend.entrepreneur.schemas.copilot_schemas import (
    CopilotConversationDetail,
    CopilotConversationSummary,
    CopilotMessage,
    CopilotMessageResponse,
)
from backend.entrepreneur.services.administrative_agent_tools_service import build_administrative_agent_tools
from backend.entrepreneur.services.compliance_agent_tools_service import build_compliance_agent_tools
from backend.entrepreneur.services.startup_offer_matching_tools_service import (
    build_voir_resultat_matching_offres_tool,
)
from backend.matching.services.chercheur_matching_tools_service import (
    build_voir_resultat_matching_chercheur_tool,
)
from backend.entrepreneur.services.project_service import get_owned_project
from backend.shared.models.user import User

_TITRE_PAR_DEFAUT = "Nouvelle conversation"
_LONGUEUR_MAX_TITRE = 60


class CopilotConversationError(Exception):
    """Erreur metier propre aux conversations du copilot (fichier dedie,

    distincte de ProjectError -- une conversation peut exister/appartenir
    au bon projet mais ne pas correspondre a ce qu'on cherche, ce n'est pas
    une erreur de projet)."""


class CopilotConversationNotFoundError(CopilotConversationError):
    pass


def get_owned_conversation(
    db: Session, user: User, project_id: UUID, conversation_id: UUID
) -> ProjectCopilotConversation:
    """Meme garde que get_owned_project, un niveau plus bas : verifie que la

    conversation existe ET appartient bien a CE projet (donc, transitivement
    via get_owned_project, a cet utilisateur) -- sans ca, deviner un UUID de
    conversation suffirait a lire la conversation d'un autre entrepreneur.
    """
    get_owned_project(db, user, project_id)
    conversation = (
        db.query(ProjectCopilotConversation)
        .filter(
            ProjectCopilotConversation.id == conversation_id,
            ProjectCopilotConversation.project_id == project_id,
        )
        .first()
    )
    if conversation is None:
        raise CopilotConversationNotFoundError("Conversation introuvable.")
    return conversation


def create_conversation(db: Session, user: User, project_id: UUID) -> CopilotConversationSummary:
    get_owned_project(db, user, project_id)
    conversation = ProjectCopilotConversation(project_id=project_id, titre=_TITRE_PAR_DEFAUT, messages=[])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return CopilotConversationSummary.model_validate(conversation)


def list_conversations(db: Session, user: User, project_id: UUID) -> list[CopilotConversationSummary]:
    get_owned_project(db, user, project_id)
    conversations = (
        db.query(ProjectCopilotConversation)
        .filter(ProjectCopilotConversation.project_id == project_id)
        # Plus recemment active en premier -- comme l'historique de Claude,
        # pas un tri par date de creation (une vieille conversation qu'on
        # reprend aujourd'hui doit remonter en haut).
        .order_by(ProjectCopilotConversation.updated_at.desc())
        .all()
    )
    return [CopilotConversationSummary.model_validate(c) for c in conversations]


def get_conversation(db: Session, user: User, project_id: UUID, conversation_id: UUID) -> CopilotConversationDetail:
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    return CopilotConversationDetail.model_validate(conversation)


def _generer_titre(premier_message: str) -> str:
    """Titre auto-genere a partir du premier message utilisateur de la

    conversation (jamais redemande a l'entrepreneur) -- simple troncature,
    pas d'appel LLM dedie : un titre approximatif suffit pour se repérer
    dans la barre laterale, un appel Groq supplementaire juste pour ca
    serait disproportionne (voir "reste sobre").
    """
    texte = premier_message.strip()
    if len(texte) <= _LONGUEUR_MAX_TITRE:
        return texte
    return texte[:_LONGUEUR_MAX_TITRE].rstrip() + "..."


def send_message(
    db: Session,
    user: User,
    project_id: UUID,
    conversation_id: UUID,
    content: str,
    tronquer_a: int | None = None,
) -> CopilotMessageResponse:
    """Ajoute `content` (nouveau message utilisateur) a la conversation,

    appelle l'agent avec l'historique + ce nouveau message, verifie
    l'ancrage de la reponse, persiste le tour complet (message utilisateur +
    reponse assistant) et renvoie la reponse au frontend.

    `tronquer_a` (voir CopilotMessageRequest) : si fourni, ne garde que les
    messages persistes [0, tronquer_a) comme historique avant d'ajouter ce
    nouveau message -- l'edition d'un message precedent (CopilotPage.tsx)
    supprime ainsi definitivement ce message et tout ce qui suivait, comme
    une regeneration apres edition. Sans ca, la troncature resterait un
    artefact purement cote client : le backend relirait quand meme tout
    l'historique complet stocke en base a chaque appel.

    CopilotAgentError se propage telle quelle jusqu'au router (voir
    copilot_router.py pour sa traduction en 502) -- si l'agent echoue, rien
    n'est persiste (le message utilisateur n'est ajoute qu'une fois la
    reponse obtenue, pas avant), pour ne jamais laisser une conversation
    avec un message utilisateur sans reponse.
    """
    conversation = get_owned_conversation(db, user, project_id, conversation_id)

    messages_persistes = conversation.messages if tronquer_a is None else conversation.messages[:tronquer_a]
    historique: list[CopilotMessage] = [CopilotMessage(**m) for m in messages_persistes]
    conversation_pour_agent: list[ConversationMessage] = [
        {"role": m.role, "content": m.content} for m in historique
    ] + [{"role": "user", "content": content}]

    seen_chunks: list[dict] = []
    tools_conformite = build_compliance_agent_tools(
        db, user, project_id, seen_source_ids=[], seen_chunks=seen_chunks
    )
    tools_reglementaire = build_administrative_agent_tools(
        db, user, project_id, seen_source_ids=[], seen_chunks=seen_chunks
    )
    # Chacun un seul tool de lecture -- voir docstring de module (CORRECTIF
    # du 26/09/2026) pour pourquoi ce ne sont plus 2 tools ajoutes au
    # toolset "conformite".
    tools_matching_chercheur = [build_voir_resultat_matching_chercheur_tool(db, project_id)]
    tools_matching_offres = [build_voir_resultat_matching_offres_tool(db, project_id)]
    result = answer_message(
        conversation_pour_agent,
        tools_conformite,
        tools_reglementaire,
        tools_matching_chercheur,
        tools_matching_offres,
    )
    verification = verifier_reponse(result.reponse, seen_chunks)

    # Jeton unique genere UNIQUEMENT quand l'agent a produit un document (voir
    # CopilotResponse.titre_document) -- jamais pour une reponse normale, pour
    # ne pas polluer les vieux messages persistes avec un champ inutile a
    # chaque tour. Adresse ce message precis independamment de sa position
    # dans le tableau (voir docstring de CopilotMessage.document_ref).
    document_ref = uuid4().hex if result.titre_document else None

    nouveau_message_utilisateur = CopilotMessage(role="user", content=content)
    nouveau_message_assistant = CopilotMessage(
        role="assistant",
        content=result.reponse,
        rediriger_vers=result.rediriger_vers,
        titre_document=result.titre_document,
        document_ref=document_ref,
        ancrage_verifie=verification.ancre if verification is not None else None,
    )
    conversation.messages = [
        *(m.model_dump() for m in historique),
        nouveau_message_utilisateur.model_dump(),
        nouveau_message_assistant.model_dump(),
    ]
    if conversation.titre == _TITRE_PAR_DEFAUT:
        conversation.titre = _generer_titre(content)
    db.add(conversation)
    db.commit()

    return CopilotMessageResponse(
        reponse=result.reponse,
        rediriger_vers=result.rediriger_vers,
        titre_document=result.titre_document,
        document_ref=document_ref,
        ancrage_verifie=nouveau_message_assistant.ancrage_verifie,
    )


def get_message_document(
    db: Session, user: User, project_id: UUID, conversation_id: UUID, document_ref: str
) -> tuple[str, str]:
    """Retrouve le message assistant portant ce `document_ref` dans la

    conversation et renvoie (titre_document, content) -- consomme par
    copilot_document_report_service.py pour construire le PDF. Cherche par
    jeton, jamais par position dans le tableau : une troncature/edition
    (tronquer_a) peut avoir change les index depuis la generation du
    document, jamais son propre jeton.
    """
    conversation = get_owned_conversation(db, user, project_id, conversation_id)
    for message in conversation.messages:
        if message.get("document_ref") == document_ref:
            return message["titre_document"], message["content"]
    raise CopilotConversationNotFoundError("Document introuvable pour cette conversation.")
