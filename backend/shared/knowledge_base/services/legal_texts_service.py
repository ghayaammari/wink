"""Persistance de `legal_texts` — pas de logique IA/API externe ici, uniquement
de la lecture/écriture DB. Le texte brut vient de
`scrapers/legifrance/legifrance_client.py`, la classification de
`agents/ingestion/legal_text_structuring_service.py` — même séparation que
`content_embeddings_service.py` (voir ce fichier).

`list_pending_validation` / `validate_legal_text` (Phase 1.5, Étapes 1.5.2/
1.5.3) vivent ici plutôt que dans un nouveau fichier : même table, même
responsabilité (persistance de legal_texts), pas une logique métier distincte
de l'upsert au-dessus.

Ne commit jamais la session : à l'appelant de décider quand committer (voir
`collect_legal_texts_formes_juridiques.py` et `legal_texts_validation_router.py`).
"""
import uuid

from sqlalchemy.orm import Session

from backend.shared.knowledge_base.models.legal_texts import LegalText


class LegalTextNotFoundError(Exception):
    """Aucune ligne `legal_texts` avec cet id."""


def get_legal_text(db: Session, *, code_source: str, article_numero: str | None) -> LegalText | None:
    """Lecture seule par (code_source, article_numero) — aucune ecriture.
    Utilisee pour sauter un appel LLM de classification quand le texte source
    n'a pas change depuis la derniere collecte (voir
    `collect_sector_insurance_recommendations.py`)."""
    return (
        db.query(LegalText)
        .filter(LegalText.code_source == code_source, LegalText.article_numero == article_numero)
        .first()
    )


def upsert_legal_text(
    db: Session,
    *,
    domaine_reglementaire: str,
    code_source: str,
    article_numero: str | None,
    texte_brut: str,
    sous_theme: str | None = None,
    forme_juridique_concernee: list[str] | None = None,
    chunking_suggere: str = "aucun",
    source_url: str | None = None,
    date_effet=None,
    date_derniere_modification=None,
) -> tuple[LegalText, bool]:
    """Insère ou met à jour la ligne identifiée par (code_source, article_numero).

    Retourne (ligne, was_created). `statut_contenu` n'est jamais un paramètre :
    toujours 'extrait_automatique' à l'insertion (voir modèle) ; sur une mise à
    jour, repasse en 'extrait_automatique' UNIQUEMENT si le contenu a réellement
    changé (même logique que RoadmapNode._upsert_node, Groupe 1) — une validation
    humaine faite sur l'ancien texte ne garantit rien sur le nouveau.
    """
    existing = (
        db.query(LegalText)
        .filter(LegalText.code_source == code_source, LegalText.article_numero == article_numero)
        .first()
    )
    values = dict(
        domaine_reglementaire=domaine_reglementaire,
        texte_brut=texte_brut,
        sous_theme=sous_theme,
        forme_juridique_concernee=forme_juridique_concernee or [],
        chunking_suggere=chunking_suggere,
        source_url=source_url,
        date_effet=date_effet,
        date_derniere_modification=date_derniere_modification,
    )
    if existing is not None:
        content_changed = any(getattr(existing, k) != v for k, v in values.items())
        for k, v in values.items():
            setattr(existing, k, v)
        if content_changed:
            existing.statut_contenu = "extrait_automatique"
        db.flush()
        return existing, False

    row = LegalText(code_source=code_source, article_numero=article_numero, **values)
    db.add(row)
    db.flush()
    return row, True


def update_texte_brut(
    db: Session,
    *,
    code_source: str,
    article_numero: str | None,
    texte_brut: str,
    date_effet=None,
) -> tuple[LegalText, bool] | None:
    """Met à jour UNIQUEMENT texte_brut (et date_effet) d'une ligne déjà
    existante — jamais sous_theme/chunking_suggere/forme_juridique_concernee,
    contrairement à upsert_legal_text qui remplace tout. Utilisée par
    `scripts/refresh_legal_texts_texte_brut.py` (re-collecte Légifrance SANS
    appel LLM, voir ce script) : on rafraîchit le texte source, on ne
    reclassifie rien.

    Retourne None si la ligne n'existe pas encore — cette fonction ne crée
    jamais de nouvelle ligne (un article vraiment nouveau nécessiterait
    sous_theme/chunking_suggere, donc un appel LLM, hors périmètre ici ;
    utiliser upsert_legal_text via collect_legal_texts_formes_juridiques.py
    pour un vrai nouvel article).

    Sinon retourne (ligne, was_changed) — même garde-fou que upsert_legal_text :
    repasse en 'extrait_automatique' UNIQUEMENT si texte_brut a réellement
    changé, une relecture humaine faite sur l'ancien texte ne garantit rien
    sur le nouveau.
    """
    row = (
        db.query(LegalText)
        .filter(LegalText.code_source == code_source, LegalText.article_numero == article_numero)
        .first()
    )
    if row is None:
        return None
    if row.texte_brut == texte_brut:
        return row, False
    row.texte_brut = texte_brut
    if date_effet is not None:
        row.date_effet = date_effet
    row.statut_contenu = "extrait_automatique"
    db.flush()
    return row, True


def list_valide_humain(db: Session) -> list[LegalText]:
    """Lignes déjà relues et confirmées (Phase 2, Étape 2.1) — seules celles-ci
    sont chunkées/embeddées, voir `chunk_and_embed_legal_texts.py`. Triées par
    ordre de collecte, même convention que `list_pending_validation`."""
    return (
        db.query(LegalText)
        .filter(LegalText.statut_contenu == "valide_humain")
        .order_by(LegalText.collecte_le)
        .all()
    )


def list_pending_validation(db: Session) -> list[LegalText]:
    """Lignes en attente de relecture humaine (Étape 1.5.2) — triées par ordre
    de collecte, comme demandé dans le plan Notion."""
    return (
        db.query(LegalText)
        .filter(LegalText.statut_contenu == "extrait_automatique")
        .order_by(LegalText.collecte_le)
        .all()
    )


def validate_legal_text(db: Session, legal_text_id: uuid.UUID, action: str) -> LegalText:
    """Étape 1.5.3 : 'valider' passe en valide_humain sans toucher
    chunking_suggere ; 'corriger' passe en valide_humain ET inverse
    chunking_suggere (aucun <-> par_alinea) — seule correction que ce
    dashboard permet (pas d'édition libre du texte ici, voir plan Notion).
    Ne commit jamais (même convention que upsert_legal_text ci-dessus) :
    au routeur de committer.
    """
    row = db.query(LegalText).filter(LegalText.id == legal_text_id).first()
    if row is None:
        raise LegalTextNotFoundError(f"legal_texts.id={legal_text_id} introuvable.")
    row.statut_contenu = "valide_humain"
    if action == "corriger":
        row.chunking_suggere = "par_alinea" if row.chunking_suggere == "aucun" else "aucun"
    db.flush()
    return row
