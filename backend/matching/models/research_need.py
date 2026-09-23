"""Table `research_needs` — service 7.7.1 (Formulaire de déclaration de

besoin scientifique, côté Entrepreneur). Vit dans `backend/matching/` et non
`backend/entrepreneur/` : c'est le point d'entrée du matching Startup ↔
Chercheur (EPIC-07), une fonctionnalité cross-acteurs — voir
Wink_architecture_fichiers.md, `backend/matching/` est le seul dossier
backend réservé à ce type de besoin.

Un projet peut déclarer plusieurs besoins (`titre` différencie) ; chacun est
la base d'un feed de matching indépendant (aucun besoin déposé = aucun feed,
logique portée par le service de matching, pas par ce modèle). `type_besoin`
distingue un problème concret à résoudre d'une expertise recherchée sans
problème précis formulé — les deux sont traités identiquement pour le
matching (même recherche par similarité côté agent), la distinction ne sert
qu'à l'affichage et à la formulation de la requête envoyée à l'agent.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ResearchNeed(Base):
    __tablename__ = "research_needs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type_besoin: Mapped[str] = mapped_column(String(20), nullable=False)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # 'ouvert' : un feed de matching est calculé pour ce besoin. 'ferme' :
    # l'entrepreneur a trouvé son chercheur ou abandonné -- le besoin reste
    # visible (historique) mais ne génère plus de feed actif (logique service,
    # pas de suppression : voir raisonnement "jamais écraser un fait" déjà
    # appliqué ailleurs dans le projet, ici transposé à "jamais supprimer une
    # démarche passée").
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ouvert")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("type_besoin IN ('probleme', 'expertise')", name="ck_research_needs_type_besoin"),
        CheckConstraint("statut IN ('ouvert', 'ferme')", name="ck_research_needs_statut"),
    )
