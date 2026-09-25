"""Persistance pure de `contract_clauses_library` — aucun appel IA/API externe
ici (voir `backend/shared/knowledge_base/services/legal_texts_service.py` pour
la même séparation sur `legal_texts`).

Upsert par (document_type, code_clause) — clé métier, pas une contrainte DB :
la table n'a volontairement pas de UniqueConstraint dessus (voir docstring du
modèle, `document_type` reste une liste ouverte). C'est donc ce module, pas la
base, qui garantit l'idempotence d'un re-seed.

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026) : `scenario` -> `code_clause`,
`scenario_description` -> `description_clause`, et `get_by_scenario` ->
`get_by_code` en conséquence — voir la docstring du modèle pour le pourquoi.
"""
from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.contract_clause_library import ContractClauseLibrary


def get_by_code(db: Session, *, document_type: str, code_clause: str) -> ContractClauseLibrary | None:
    return (
        db.query(ContractClauseLibrary)
        .filter(
            ContractClauseLibrary.document_type == document_type,
            ContractClauseLibrary.code_clause == code_clause,
        )
        .first()
    )


def list_hors_liste(db: Session, *, document_type: str, codes_gardes: set[str]) -> list[ContractClauseLibrary]:
    """Clauses de `document_type` absentes du clausier courant (retirées ou
    exclues) — à supprimer par l'appelant, avec leurs embeddings."""
    return (
        db.query(ContractClauseLibrary)
        .filter(ContractClauseLibrary.document_type == document_type, ContractClauseLibrary.code_clause.notin_(codes_gardes))
        .all()
    )


def upsert_clause(
    db: Session,
    *,
    document_type: str,
    code_clause: str,
    description_clause: str,
    titre_clause: str,
    texte_clause: str,
    variables_requises: list[dict],
    source_modele: str,
    verifie_par_professionnel: bool = False,
    forme_juridique_concernee: str | None = None,
) -> ContractClauseLibrary:
    existing = get_by_code(db, document_type=document_type, code_clause=code_clause)
    if existing is not None:
        # Un re-seed après correction du texte source repasse en 'extrait_automatique' :
        # une validation humaine faite sur l'ancien texte ne garantit rien sur le nouveau
        # (même règle que legal_texts_service.upsert_legal_text).
        content_changed = existing.texte_clause != texte_clause or existing.titre_clause != titre_clause
        existing.description_clause = description_clause
        existing.titre_clause = titre_clause
        existing.texte_clause = texte_clause
        existing.variables_requises = variables_requises
        existing.source_modele = source_modele
        existing.verifie_par_professionnel = verifie_par_professionnel
        existing.forme_juridique_concernee = forme_juridique_concernee
        if content_changed:
            existing.statut_contenu = "extrait_automatique"
        db.flush()
        return existing

    row = ContractClauseLibrary(
        document_type=document_type,
        code_clause=code_clause,
        description_clause=description_clause,
        titre_clause=titre_clause,
        texte_clause=texte_clause,
        variables_requises=variables_requises,
        source_modele=source_modele,
        verifie_par_professionnel=verifie_par_professionnel,
        forme_juridique_concernee=forme_juridique_concernee,
    )
    db.add(row)
    db.flush()
    return row
