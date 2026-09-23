"""Table `project_copilot_conversations` -- une conversation du copilot

conformite (agents/orchestrator/copilot_agent_service.py). Revient sur la
decision V1 "pas de persistance, le frontend renvoie tout l'historique a
chaque appel" (voir ancienne docstring de copilot_service.py) : demande
explicite du 20/09/2026 -- plusieurs conversations distinctes par projet,
listees dans une barre laterale (comme l'historique de Claude), pas
seulement une session ephemere perdue au rechargement.

Une ligne = une conversation entiere. `messages` est un JSONB (liste
d'objets {role, content, rediriger_vers?, rapportDisponible?,
ancrage_verifie?}) plutot qu'une table `copilot_messages` a part : le
contrat HTTP existant envoie/recoit deja le tableau complet a chaque appel
(voir copilot_schemas.py), et rien aujourd'hui n'a besoin d'interroger un
message individuellement (recherche, pagination) -- une table dediee serait
de la complexite anticipee sans besoin reel actuel (voir "reste sobre").
A reconsiderer si un jour il faut chercher dans les messages ou paginer une
tres longue conversation.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectCopilotConversation(Base):
    __tablename__ = "project_copilot_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Titre auto-genere a partir du premier message utilisateur (voir
    # copilot_service.py::_generer_titre) -- jamais demande explicitement a
    # l'entrepreneur, comme les titres de conversation de Claude.
    titre: Mapped[str] = mapped_column(Text, nullable=False, server_default="Nouvelle conversation")
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # Mise a jour a chaque nouveau message (pas seulement a la creation) --
    # c'est ce qui permet de trier la liste des conversations par activite
    # recente dans la barre laterale, comme Claude.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
