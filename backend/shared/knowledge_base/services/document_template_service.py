"""Persistance pure de `document_templates` — squelette structurel d'un type de
document (Phase collecte, Groupe 5). Upsert par (document_type, ordre), qui
EST la UniqueConstraint DB (uq_document_templates_type_ordre) — contrairement à
contract_clauses_library, la contrainte d'idempotence est donc imposée par la
base elle-même, pas seulement par ce module.

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026) : `nom_section` -> `code_section`,
`type_contenu` -> `comportement_section` — voir la docstring du modèle pour le
pourquoi.
"""
from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.document_template import DocumentTemplate


def get_by_ordre(db: Session, *, document_type: str, ordre: int) -> DocumentTemplate | None:
    return (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type, DocumentTemplate.ordre == ordre)
        .first()
    )


def list_sections(db: Session, *, document_type: str) -> list[DocumentTemplate]:
    return (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type)
        .order_by(DocumentTemplate.ordre)
        .all()
    )


def delete_hors_liste(db: Session, *, document_type: str, ordres_gardes: set[int]) -> list[str]:
    """Supprime les sections de `document_type` dont l'`ordre` n'est plus dans
    le squelette courant — indispensable quand le squelette RÉTRÉCIT (upsert
    par position : sans ça, les positions en trop resteraient et le moteur les
    poserait à l'utilisateur). Renvoie les `code_section` supprimés."""
    obsoletes = (
        db.query(DocumentTemplate)
        .filter(DocumentTemplate.document_type == document_type, DocumentTemplate.ordre.notin_(ordres_gardes))
        .all()
    )
    codes = [s.code_section for s in obsoletes]
    for section in obsoletes:
        db.delete(section)
    db.flush()
    return codes


def upsert_section(
    db: Session,
    *,
    document_type: str,
    code_section: str,
    ordre: int,
    comportement_section: str,
    obligatoire: bool,
    reference_type: str | None = None,
    reference_id=None,
    variantes_candidates: list[str] | None = None,
    texte_statique: str | None = None,
    formes_juridiques_concernees: list[str] | None = None,
    # AJOUTÉS (20/09/2026) : necessite_investisseurs (migration d3a7c5e8f1b4)
    # et depend_de_section/depend_de_variantes (migration f6b3e9a2c5d7)
    # existaient déjà sur le modèle et dans _applicable() mais n'étaient
    # jamais câblés ici -- trou trouvé en relecture de contrôle, corrigé
    # avant qu'il ne bloque silencieusement le seed des nouvelles sections.
    necessite_investisseurs: bool = False,
    necessite_absence_investisseurs: bool = False,
    depend_de_section: str | None = None,
    depend_de_variantes: list[str] | None = None,
    titre_affiche: str | None = None,
    explication: str | None = None,
) -> DocumentTemplate:
    existing = get_by_ordre(db, document_type=document_type, ordre=ordre)
    values = dict(
        code_section=code_section,
        comportement_section=comportement_section,
        obligatoire=obligatoire,
        reference_type=reference_type,
        reference_id=reference_id,
        variantes_candidates=variantes_candidates,
        texte_statique=texte_statique,
        formes_juridiques_concernees=formes_juridiques_concernees,
        necessite_investisseurs=necessite_investisseurs,
        necessite_absence_investisseurs=necessite_absence_investisseurs,
        depend_de_section=depend_de_section,
        depend_de_variantes=depend_de_variantes,
        titre_affiche=titre_affiche,
        explication=explication,
    )
    if existing is not None:
        for key, value in values.items():
            setattr(existing, key, value)
        db.flush()
        return existing

    row = DocumentTemplate(document_type=document_type, ordre=ordre, **values)
    db.add(row)
    db.flush()
    return row
