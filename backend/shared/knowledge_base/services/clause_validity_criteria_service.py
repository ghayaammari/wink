"""Persistance pure de `clause_validity_criteria`. Upsert par (clause_library_id,
type_critere) — clé métier, pas de UniqueConstraint DB dessus (une clause pourra
avoir plusieurs critères du même type dans un futur incrément, ex. deux plafonds
différents selon la forme juridique ; figer une contrainte unique aujourd'hui
casserait ce cas sans bénéfice actuel).
"""
from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.clause_validity_criteria import ClauseValidityCriterion


def list_for_clause(db: Session, *, clause_library_id) -> list[ClauseValidityCriterion]:
    return (
        db.query(ClauseValidityCriterion)
        .filter(ClauseValidityCriterion.clause_library_id == clause_library_id)
        .all()
    )


def get_by_type(db: Session, *, clause_library_id, type_critere: str) -> ClauseValidityCriterion | None:
    return (
        db.query(ClauseValidityCriterion)
        .filter(
            ClauseValidityCriterion.clause_library_id == clause_library_id,
            ClauseValidityCriterion.type_critere == type_critere,
        )
        .first()
    )


def upsert_criterion(
    db: Session,
    *,
    clause_library_id,
    type_critere: str,
    description_critere: str,
    base_legale: str,
    valeur_limite: dict | None = None,
) -> ClauseValidityCriterion:
    existing = get_by_type(db, clause_library_id=clause_library_id, type_critere=type_critere)
    if existing is not None:
        existing.description_critere = description_critere
        existing.base_legale = base_legale
        existing.valeur_limite = valeur_limite
        db.flush()
        return existing

    row = ClauseValidityCriterion(
        clause_library_id=clause_library_id,
        type_critere=type_critere,
        description_critere=description_critere,
        base_legale=base_legale,
        valeur_limite=valeur_limite,
    )
    db.add(row)
    db.flush()
    return row
