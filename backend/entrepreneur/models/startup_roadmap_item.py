"""Table `startup_roadmap_items` — progression d'un projet précis sur le graphe
`roadmap_nodes`. Une ligne par (projet, nœud), peuplée pour les 24 nœuds dès le
premier accès à la roadmap du projet (voir roadmap_service._ensure_items). Le
filtrage par `roadmap_nodes.applicable_if` se fait à l'affichage (service
1.1.11, roadmap_service._evaluate_applicable_if), jamais à la création.
(Modification réalisé par OPENCODE : commentaire mis à jour après
implémentation du filtrage.)
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class StartupRoadmapItem(Base):
    __tablename__ = "startup_roadmap_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("roadmap_nodes.id", ondelete="CASCADE"), nullable=False
    )
    # Valeurs actées (voir "Wink — Schémas Incrément 1 v3" + "Plan d'action
    # pré-création : spécification", points à trancher) : verrouille (défaut,
    # dépendances pas encore satisfaites) -> a_faire -> en_cours -> termine,
    # ou non_necessaire (devenu inapplicable après changement de profil).
    # Déverrouillage géré par roadmap_service._cascade_unlock, jamais par le
    # client (voir RoadmapItemUpdate côté schémas : "verrouille" n'y est pas
    # settable).
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="verrouille")
    # Copie figée du contenu de RoadmapNode au moment de l'assignation — un projet garde
    # le texte qu'il a vu même si `roadmap_nodes` est corrigé/revalidé plus tard.
    node_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Preuve documentaire optionnelle (ex: statuts signés, Kbis) — FK côté
    # startup_roadmap_items plutôt qu'un node_id sur documents : documents reste
    # générique (sert aussi à 0.0.2), ne doit pas connaître le concept de roadmap.
    proof_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("project_id", "node_id", name="uq_startup_roadmap_items_project_node"),
        CheckConstraint(
            "statut IN ('verrouille', 'a_faire', 'en_cours', 'termine', 'non_necessaire')",
            name="ck_startup_roadmap_items_statut",
        ),
    )
