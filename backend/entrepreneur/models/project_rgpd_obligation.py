"""Table `project_rgpd_obligations` — service 3.3.1 (RGPD). Table "vivante" :
1 ligne par obligation applicable à un projet, avec son statut coché par
l'entrepreneur (vert une fois fait). Remplace l'ancien design à 2 tables
(catalogue `compliance_obligations` + instances) après discussion — décision
actée : catalogue jugé non nécessaire, l'agent conformité régénère/complète
directement cette table à partir du profil + des embeddings RGPD, pas besoin
d'un référentiel intermédiaire pré-rempli.

"Jamais écraser un fait" (même règle que `startup_roadmap_items.statut`,
Groupe 1) : une régénération de l'agent ne doit jamais faire repasser une
ligne `fait` à `a_faire` — logique portée par le service, pas par ce modèle
(voir project_rgpd_obligation_service.py, à écrire).

`nom` sert de clé de correspondance lors d'une mise à jour incrémentale
(changement mineur de profil) : dette technique assumée (fragile si l'agent
reformule différemment le même nom d'une régénération à l'autre) — acceptée
tant que les changements de profil restent rares (voir discussion, décision
du profil non capturé à l'onboarding).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectRgpdObligation(Base):
    __tablename__ = "project_rgpd_obligations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    # Explication complète pour l'utilisateur (jamais un simple ordre, voir
    # discussion : "il faut une explication pour le user et non pas quelque
    # chose d'ordre seulement").
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, server_default="a_faire")
    # Justification sourcée — jamais d'obligation sans texte source réel (voir
    # règle du projet : "aucune réponse réglementaire sans source vérifiable").
    legal_text_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("legal_texts.id"), nullable=True
    )
    # Ajoute le 17/09/2026 (demande : regrouper visuellement les obligations
    # liees a une AIPD a part du reste) - booleen simple plutot qu'une
    # categorie/enum a plusieurs valeurs : le seul besoin actuel est binaire
    # (lie a l'AIPD ou non), une taxonomie complete par theme (registre,
    # securite, sous-traitance...) ajouterait de la surface d'hallucination
    # pour le LLM sans benefice tant qu'aucun autre regroupement n'est demande.
    # A etendre vers un vrai champ `categorie` uniquement si un besoin de
    # regroupement par plusieurs themes apparait reellement plus tard.
    lie_a_aipd: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("project_id", "nom", name="uq_project_rgpd_obligations_project_nom"),
        CheckConstraint("statut IN ('a_faire', 'fait')", name="ck_project_rgpd_obligations_statut"),
    )
