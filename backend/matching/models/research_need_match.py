"""Table `research_need_matches` — résultat du matching_agent (recherche →
startup) pour un besoin donné (research_needs, service 7.7.2). Vit dans
`backend/matching/` comme research_need.py (cross-acteurs, même règle —
voir Wink_architecture_fichiers.md).

Un besoin = un feed unique (UNIQUE research_need_id) : régénérer écrase le
résultat précédent, même convention que project_fintech_gap_analysis
(upsert_result, pas de règle "jamais écraser un fait" ici — le matching
doit refléter le pool de chercheurs actuel au moment du clic, pas un
historique).

`matches` est une liste JSONB déjà triée par rang plutôt qu'une table à
part par match : un feed entier est généré/lu/écrasé en un seul bloc,
jamais un match individuel modifié seul — même raisonnement que le champ
`obligations` sur project_fintech_gap_analysis.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ResearchNeedMatch(Base):
    __tablename__ = "research_need_matches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    research_need_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_needs.id", ondelete="CASCADE"), nullable=False
    )
    # Liste ordonnée par rang, chaque élément :
    # {researcher_profile_id, nom, rang, niveau_pertinence, explication} —
    # voir agents/matching_agent/chercheur_matching_service.py pour le
    # schéma Pydantic exact produit par l'agent.
    matches: Mapped[list] = mapped_column(JSONB, nullable=False)
    synthese: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("research_need_id", name="uq_research_need_matches_research_need_id"),)
