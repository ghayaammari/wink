"""Schemas Pydantic pour le copilot conformite -- conversations (CRUD) et

envoi de message (POST .../copilot/conversations/{id}/message). Voir
agents/orchestrator/copilot_agent_service.py pour le schema de sortie brut
de l'agent (CopilotResponse) et grounding_verification_service.py pour
VerificationAncrage -- non repris ici a l'identique : cette couche HTTP
n'expose que ce dont le frontend a besoin (reponse + rediriger_vers +
ancrage_verifie en bool, pas le detail des affirmations non etayees, qui ne
sert qu'au log serveur pour l'instant, voir copilot_service.py).
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

CopilotRole = Literal["user", "assistant"]
DomaineRedirection = Literal["rgpd", "ai-act", "secteur"]
RapportDomaine = Literal["rgpd", "ai-act", "healthtech", "fintech"]


class CopilotMessage(BaseModel):
    role: CopilotRole
    content: str
    # Presents uniquement sur un message assistant deja produit, jamais sur
    # le nouveau message utilisateur envoye par le frontend -- stockes tels
    # quels dans `messages` (JSONB, voir ProjectCopilotConversation) pour
    # restituer l'historique a l'identique a la reouverture d'une
    # conversation, sans avoir a rejouer l'agent.
    rediriger_vers: DomaineRedirection | None = None
    rapport_disponible: RapportDomaine | None = None
    ancrage_verifie: bool | None = None


class CopilotMessageRequest(BaseModel):
    # Le nouveau message utilisateur uniquement (role="user") -- contrairement
    # a la V1 ephemere, l'historique precedent est desormais lu depuis la
    # conversation persistee cote backend, pas renvoye par le frontend a
    # chaque appel (voir copilot_service.py::send_message).
    content: str = Field(min_length=1)
    # Si fourni, ne conserve que les messages persistes d'index [0, tronquer_a)
    # avant d'ajouter ce nouveau message -- utilise uniquement par "editer un
    # message precedent et renvoyer" (voir CopilotPage.tsx) : supprime ce
    # message et tout ce qui suivait, comme une regeneration apres edition.
    # None (defaut) = envoi normal, conserve tout l'historique existant.
    tronquer_a: int | None = Field(default=None, ge=0)


class CopilotMessageResponse(BaseModel):
    reponse: str
    rediriger_vers: DomaineRedirection | None = None
    # None = aucune verification effectuee (reponse generale sans recherche
    # dans le corpus, rien a verifier) ou verification indisponible (echec
    # non bloquant, voir grounding_verification_service.py) -- distinct de
    # False (verification faite, affirmations non etayees trouvees).
    ancrage_verifie: bool | None = None


class CopilotConversationSummary(BaseModel):
    id: UUID
    titre: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CopilotConversationDetail(CopilotConversationSummary):
    messages: list[CopilotMessage]
