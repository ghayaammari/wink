"""Table `project_certification_estimations` — service 3.3.11. 1 ligne par

couple (projet, type de certification) déjà généré : délai et coût estimés
du parcours complet, avec justification textuelle. Table séparée de
`project_certification_obligations` (pas une colonne dessus) car c'est une
estimation globale du parcours, pas une propriété d'une étape individuelle.

Bornes min/max plutôt qu'une valeur unique : un délai ou un coût de
certification n'est jamais un chiffre exact avant l'audit réel (dépend de
l'auditeur retenu, de l'état de préparation constaté sur place) -- donner
une fourchette évite de laisser croire à une précision que le corpus ne
permet pas (même logique que score=None dans compliance_score_service.py :
ne jamais donner un chiffre plus précis que ce qu'on sait vraiment).

Jamais régénérée automatiquement (mêmes garde-fous que les autres domaines
compliance) : seule une action explicite de l'entrepreneur déclenche un
nouveau calcul, qui remplace la ligne existante (UniqueConstraint sur
project_id + type_certification, pas d'historique -- contrairement à RGPD
qui garde un historique des obligations, une ré-estimation de délai/coût
n'a pas besoin d'être tracée dans le temps pour ce service).

`type_certification` limité à 'secnumcloud' en V1 (voir migration
q4d6f8a0b2c4) -- même logique d'extension future que ProjectCertificationObligation.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.database import Base


class ProjectCertificationEstimation(Base):
    __tablename__ = "project_certification_estimations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type_certification: Mapped[str] = mapped_column(String(20), nullable=False)
    delai_mois_min: Mapped[int] = mapped_column(Integer, nullable=False)
    delai_mois_max: Mapped[int] = mapped_column(Integer, nullable=False)
    cout_estime_min: Mapped[int] = mapped_column(Integer, nullable=False)
    cout_estime_max: Mapped[int] = mapped_column(Integer, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "type_certification", name="uq_project_certification_estimations_project_type"
        ),
        CheckConstraint(
            "type_certification IN ('secnumcloud')",
            name="ck_project_certification_estimations_type",
        ),
    )
