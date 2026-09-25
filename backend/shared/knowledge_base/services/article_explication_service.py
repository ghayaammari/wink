"""Persistance pure de `article_explications` (aucun appel IA ici — voir
agents/contract_agent/article_explanation_service.py). Upsert par
(document_type, code_facultatif)."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.article_explication import ArticleExplication


def get(db: Session, *, document_type: str, code_facultatif: str) -> ArticleExplication | None:
    return (
        db.query(ArticleExplication)
        .filter(ArticleExplication.document_type == document_type, ArticleExplication.code_facultatif == code_facultatif)
        .first()
    )


def upsert_generee(
    db: Session, *, document_type: str, code_facultatif: str, texte: str, ecraser_validee: bool = False
) -> tuple[ArticleExplication, bool]:
    """Enregistre une explication générée (`extrait_automatique`). Ne remplace
    JAMAIS une explication déjà validée par un humain, sauf `ecraser_validee`
    (elle repasse alors en `extrait_automatique`, à relire de nouveau).
    Renvoie (ligne, écrite?)."""
    ligne = get(db, document_type=document_type, code_facultatif=code_facultatif)
    if ligne is not None and ligne.statut_contenu == "valide_humain" and not ecraser_validee:
        return ligne, False
    if ligne is None:
        ligne = ArticleExplication(document_type=document_type, code_facultatif=code_facultatif, texte=texte)
        db.add(ligne)
    else:
        ligne.texte = texte
        ligne.genere_le = func.now()
        ligne.valide_le = None
    ligne.statut_contenu = "extrait_automatique"
    db.flush()
    return ligne, True


def valider(db: Session, *, document_type: str, code_facultatif: str, texte_corrige: str | None = None) -> ArticleExplication:
    """Relecture humaine : marque l'explication `valide_humain`, en remplaçant
    son texte si une correction est fournie. Lève LookupError si absente."""
    ligne = get(db, document_type=document_type, code_facultatif=code_facultatif)
    if ligne is None:
        raise LookupError(f"Aucune explication pour '{code_facultatif}' ({document_type}) — la générer d'abord.")
    if texte_corrige is not None and texte_corrige.strip():
        ligne.texte = texte_corrige.strip()
    ligne.statut_contenu = "valide_humain"
    ligne.valide_le = func.now()
    db.flush()
    return ligne


def list_all(db: Session, *, document_type: str) -> list[ArticleExplication]:
    return (
        db.query(ArticleExplication)
        .filter(ArticleExplication.document_type == document_type)
        .order_by(ArticleExplication.code_facultatif)
        .all()
    )


def textes_valides(db: Session, *, document_type: str) -> dict[str, str]:
    """{code_facultatif: texte} des seules explications relues et validées —
    ce qui est affiché à l'utilisateur."""
    lignes = (
        db.query(ArticleExplication)
        .filter(ArticleExplication.document_type == document_type, ArticleExplication.statut_contenu == "valide_humain")
        .all()
    )
    return {ligne.code_facultatif: ligne.texte for ligne in lignes}
