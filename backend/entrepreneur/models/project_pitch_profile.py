"""Table `project_pitch_profiles` — contenu saisi par l'entrepreneur pour le

generateur de pitch deck (service 6.6.2, EPIC-06/I5). Une ligne par projet.

Ne duplique jamais ce que "Mon projet" connait deja : le nom, le pitch en
une ligne (ProjectPublicProfile.public_summary) et le logo
(ProjectPublicProfile.logo_url) sont relus depuis la vitrine publique au
moment de la generation (voir pitch_deck_service.py), et l'equipe est relue
depuis project_associates (ProjectAssociate.nom_complet/fonction_dirigeant) —
jamais ressaisie ici. Seuls les champs vraiment nouveaux (probleme, solution,
marche...) vivent dans cette table.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectPitchProfile(Base):
    __tablename__ = "project_pitch_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    probleme: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    marche: Mapped[str | None] = mapped_column(Text, nullable=True)
    modele_economique: Mapped[str | None] = mapped_column(Text, nullable=True)
    concurrence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Texte libre (metriques + jalons en une saisie) plutot qu'un sous-formulaire
    # structure : l'agent (pitch_deck_content_service.py) se charge de le
    # reformuler en puces/chiffres pour la diapositive -- eviter un formulaire
    # a tiroirs pour une premiere version (voir "reste sobre").
    traction: Mapped[str | None] = mapped_column(Text, nullable=True)
    financements: Mapped[str | None] = mapped_column(Text, nullable=True)
    roadmap: Mapped[str | None] = mapped_column(Text, nullable=True)
    demande_investissement: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
