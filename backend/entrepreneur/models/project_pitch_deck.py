"""Table `project_pitch_decks` — dernier contenu de pitch deck genere par

l'agent (agents/pitch_deck_agent/) pour un projet. Une ligne par projet,
ECRASEE a chaque regeneration explicite (bouton "Generer/Regenerer", voir
pitch_router.py) — pas de versioning/historique, meme choix que les
diagnostics de conformite (ProjectAiActObligation etc. n'archivent que les
obligations retirees, jamais tout le rapport).

Le fichier PPTX lui-meme n'est PAS stocke ici : il est re-rendu a la volee a
partir de `content` a chaque telechargement (pitch_deck_renderer_service.py,
pur python-pptx, deterministe, pas d'appel LLM) — meme principe que les
rapports PDF RGPD/AI Act (compliance_report_service.py), qui ne persistent
jamais le PDF non plus.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectPitchDeck(Base):
    __tablename__ = "project_pitch_decks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # DeckContentModel.model_dump(mode="json") (agents/pitch_deck_agent/deck_schema.py) —
    # jamais lu/filtre par colonne ici, uniquement par le service qui connait le schema.
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
