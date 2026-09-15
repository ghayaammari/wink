"""Table `notifications` — objet métier générique, pas propre au Kbis. Un
changement de statut seul (ex. `kbis_verification_status = 'verifie'`) ne
"notifie" pas : il faut une ligne visible, avec un message et un lien vers
l'action suivante. Premier usage : service 1.1.9 (notification de
disponibilité du Kbis, Parcours A), mais table pensée dès le départ pour
être réutilisée par toute future notification projet (voir page Notion
"Récapitulatif — Décisions Entrepreneur (Groupe 4 + vérification légale)").
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Pas de CHECK de valeurs ici — un seul type existe pour l'instant
    # ('kbis_disponible', posé par 1.1.9). À contraindre le jour où plusieurs
    # types coexistent et qu'une liste fermée a du sens.
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Pointe vers la prochaine étape de la roadmap à enchaîner (ex:
    # "e18_deblocage_fonds") — permet un lien cliquable direct depuis la
    # notification. Pas de ondelete : si le nœud roadmap référencé disparaît,
    # une notification déjà créée ne doit pas être supprimée silencieusement
    # avec lui (même raisonnement que kbis_document_id sur ProjectLegalProfile).
    node_id_suivant: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("roadmap_nodes.id"), nullable=True
    )
    lue: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
