"""Table `pacte_fondateurs_response_sources` -- les sources citees par une
reponse du copilot (traçabilite, contrainte produit "jamais inventer une
obligation sans source verifiable", voir Wink_context_project.md).

`source_type`/`source_id` polymorphe, meme convention que
`content_embeddings` (source_type='legal_texts', source_id=<uuid du
legal_texts cite>) -- pas de vraie FK possible pour la meme raison
(source_id peut pointer vers plusieurs tables differentes).

Voir docstring de pacte_fondateurs_conversation.py pour l'isolation
volontaire de ce dossier.
"""
import uuid

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class PacteFondateursResponseSource(Base):
    __tablename__ = "pacte_fondateurs_response_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    response_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pacte_fondateurs_responses.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
