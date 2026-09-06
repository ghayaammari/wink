"""Service métier — researcher_field_values.

Centralise le mécanisme polymorphe de traçabilité/validation, réutilisé par
le profil chercheur (affiliation, research_domains, résumés) et par les
travaux de recherche (paper_summary, methodology...). Un seul endroit pour
la logique confirm/reject/supersede/matérialisation, plutôt que dupliquée
dans researcher_profile_service ET research_work_service.
"""
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.chercheur.models.research_work import ResearchWork
from backend.chercheur.models.researcher_field_value import ResearcherFieldValue
from backend.chercheur.models.researcher_profile import ResearcherProfile

# Champs à valeur unique : une nouvelle valeur confirmée remplace l'ancienne
# (l'ancienne passe à 'superseded'). Absent de cette liste = multi-valeur,
# stocké comme liste JSON sur la table d'origine (ex: research_domains,
# application_domains).
SINGLE_VALUE_FIELDS = {
    "affiliation",
    "expertise_summary",
    "research_work_summary",
    "paper_summary",
    "methodology",
    # Champs factuels d'un dépôt manuel (titre, résumé fourni par les
    # auteurs, revue, doi, type de publication) — désormais soumis au même
    # cycle de validation que les champs générés (voir DECISIONS.md).
    # 'authors' est volontairement absent : multi-valeur, chaque auteur
    # devient sa propre ligne, comme application_domains/research_domains.
    "title",
    "abstract",
    "venue",
    "doi",
    "publication_type",
}


class FieldValueNotFoundError(Exception):
    pass


class InvalidFieldValueStateError(Exception):
    """Tentative de confirmer/rejeter une ligne qui n'est plus pending_confirmation."""


def _get_target_model(entity_type: str):
    return ResearcherProfile if entity_type == "researcher_profile" else ResearchWork


def _materialize(db: Session, field_value: ResearcherFieldValue) -> None:
    """Écrit la valeur confirmée sur la table d'origine (profil ou travail)."""
    model = _get_target_model(field_value.entity_type)
    target = db.get(model, field_value.entity_id)
    if target is None:
        return  # entité supprimée entre-temps — rien à matérialiser

    if field_value.field_name in SINGLE_VALUE_FIELDS:
        setattr(target, field_value.field_name, field_value.field_value)
    else:
        current = list(getattr(target, field_value.field_name, None) or [])
        if field_value.field_value not in current:
            current.append(field_value.field_value)
        setattr(target, field_value.field_name, current)


def _supersede_existing(db: Session, entity_type: str, entity_id: uuid.UUID, field_name: str) -> None:
    existing = (
        db.query(ResearcherFieldValue)
        .filter_by(entity_type=entity_type, entity_id=entity_id, field_name=field_name, validation_status="confirmed")
        .all()
    )
    for row in existing:
        row.validation_status = "superseded"


def add_value(
    db: Session,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    field_name: str,
    field_value: str,
    source: str,
) -> ResearcherFieldValue:
    """Crée une ligne. Si source == 'user_added', confirmée et matérialisée
    immédiatement (règle métier : une saisie directe de l'utilisateur n'a pas
    besoin de validation supplémentaire). Ne fait pas de commit — à la charge
    de l'appelant (permet de grouper plusieurs opérations en une transaction).

    Cas limite (même traitement que edit_value, voir plus bas) : une ligne
    identique (entity_type, entity_id, field_name, field_value) existe déjà,
    peu importe son statut actuel — la contrainte UNIQUE l'interdit sinon.
    Se produit par exemple si l'onboarding est rappelé deux fois avec la même
    affiliation (retry réseau, re-complétion après un échec partiel), ou si
    une extraction retombe deux fois sur le même texte généré. On réactive la
    ligne existante plutôt que d'échouer sur un IntegrityError."""
    validation_status = "confirmed" if source == "user_added" else "pending_confirmation"

    existing = (
        db.query(ResearcherFieldValue)
        .filter_by(entity_type=entity_type, entity_id=entity_id, field_name=field_name, field_value=field_value)
        .first()
    )
    if existing is not None:
        if validation_status == "confirmed":
            if field_name in SINGLE_VALUE_FIELDS:
                _supersede_existing(db, entity_type, entity_id, field_name)
            existing.validation_status = "confirmed"
            existing.source = source
            db.flush()
            _materialize(db, existing)
        else:
            existing.validation_status = "pending_confirmation"
            existing.source = source
            db.flush()
        return existing

    if validation_status == "confirmed" and field_name in SINGLE_VALUE_FIELDS:
        _supersede_existing(db, entity_type, entity_id, field_name)

    value = ResearcherFieldValue(
        entity_type=entity_type,
        entity_id=entity_id,
        field_name=field_name,
        field_value=field_value,
        source=source,
        validation_status=validation_status,
    )
    db.add(value)
    try:
        db.flush()  # nécessaire pour obtenir value.id avant matérialisation
    except IntegrityError:
        # Race condition : le check "existing" ci-dessus et cet INSERT ne
        # sont pas atomiques. Si une extraction concurrente pour le même
        # profil (ex: page rechargée pendant qu'une extraction tourne déjà,
        # qui réactive le bouton "Extraire" côté frontend) a inséré EXACTEMENT
        # la même ligne entre les deux, le flush échoue ici avec la même
        # contrainte UNIQUE. On annule cette tentative et on récupère la
        # ligne que l'autre transaction vient de committer, plutôt que de
        # laisser planter tout le job pour une valeur déjà présente.
        db.rollback()
        existing = (
            db.query(ResearcherFieldValue)
            .filter_by(entity_type=entity_type, entity_id=entity_id, field_name=field_name, field_value=field_value)
            .first()
        )
        if existing is None:
            raise  # pas la race anticipée — erreur réellement inattendue, à ne pas masquer
        return existing

    if validation_status == "confirmed":
        _materialize(db, value)

    return value


def confirm_value(db: Session, field_value_id: uuid.UUID) -> ResearcherFieldValue:
    value = db.get(ResearcherFieldValue, field_value_id)
    if value is None:
        raise FieldValueNotFoundError(f"researcher_field_value {field_value_id} introuvable")
    if value.validation_status != "pending_confirmation":
        raise InvalidFieldValueStateError(
            f"Impossible de confirmer une valeur au statut '{value.validation_status}'"
        )

    if value.field_name in SINGLE_VALUE_FIELDS:
        _supersede_existing(db, value.entity_type, value.entity_id, value.field_name)

    value.validation_status = "confirmed"
    db.flush()
    _materialize(db, value)
    return value


def reject_value(db: Session, field_value_id: uuid.UUID) -> ResearcherFieldValue:
    value = db.get(ResearcherFieldValue, field_value_id)
    if value is None:
        raise FieldValueNotFoundError(f"researcher_field_value {field_value_id} introuvable")
    if value.validation_status != "pending_confirmation":
        raise InvalidFieldValueStateError(
            f"Impossible de rejeter une valeur au statut '{value.validation_status}'"
        )
    value.validation_status = "rejected"
    db.flush()
    return value


def list_pending_for_entity(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[ResearcherFieldValue]:
    return (
        db.query(ResearcherFieldValue)
        .filter_by(entity_type=entity_type, entity_id=entity_id, validation_status="pending_confirmation")
        .all()
    )


def list_all_for_entity(db: Session, entity_type: str, entity_id: uuid.UUID) -> list[ResearcherFieldValue]:
    """Tous les champs générés non périmés (pending + confirmed + rejected),
    à l'inverse de list_pending_for_entity qui ne renvoie que les pending —
    nécessaire pour que le frontend garde les champs visibles après validation."""
    return (
        db.query(ResearcherFieldValue)
        .filter(
            ResearcherFieldValue.entity_type == entity_type,
            ResearcherFieldValue.entity_id == entity_id,
            ResearcherFieldValue.validation_status != "superseded",
        )
        .order_by(ResearcherFieldValue.field_name, ResearcherFieldValue.created_at)
        .all()
    )


def edit_value(db: Session, field_value_id: uuid.UUID, new_field_value: str) -> ResearcherFieldValue:
    """Corrige un champ généré (pending ou déjà confirmé) : marque l'ancienne
    ligne comme superseded et crée une nouvelle valeur user_added, confirmée
    et matérialisée immédiatement — même logique que toute saisie manuelle,
    pas de mécanisme séparé pour "l'édition"."""
    original = db.get(ResearcherFieldValue, field_value_id)
    if original is None:
        raise FieldValueNotFoundError(f"researcher_field_value {field_value_id} introuvable")
    if original.validation_status not in ("pending_confirmation", "confirmed"):
        raise InvalidFieldValueStateError(
            f"Impossible de corriger une valeur au statut '{original.validation_status}'"
        )

    # Cas limite : l'utilisateur ouvre "Modifier" et enregistre sans rien
    # changer. Rien à créer — juste confirmer si ce n'était pas déjà fait.
    if new_field_value == original.field_value:
        if original.validation_status == "pending_confirmation":
            return confirm_value(db, field_value_id)
        return original

    original.validation_status = "superseded"
    db.flush()

    # Cas limite : la nouvelle valeur correspond à une ligne qui existe déjà
    # pour cette entité/field_name (ex: l'utilisateur revient à un texte
    # précédent, ou redépose deux fois la même correction). La contrainte
    # UNIQUE (entity_type, entity_id, field_name, field_value) l'interdit
    # peu importe le statut de cette ligne existante — on la réactive au
    # lieu d'en insérer une deuxième identique.
    existing = (
        db.query(ResearcherFieldValue)
        .filter_by(
            entity_type=original.entity_type,
            entity_id=original.entity_id,
            field_name=original.field_name,
            field_value=new_field_value,
        )
        .first()
    )
    if existing is not None:
        if existing.field_name in SINGLE_VALUE_FIELDS:
            _supersede_existing(db, existing.entity_type, existing.entity_id, existing.field_name)
        existing.validation_status = "confirmed"
        existing.source = "user_added"
        db.flush()
        _materialize(db, existing)
        return existing

    return add_value(
        db,
        entity_type=original.entity_type,
        entity_id=original.entity_id,
        field_name=original.field_name,
        field_value=new_field_value,
        source="user_added",
    )
    
def replace_multi_value(
    db: Session, *, entity_type: str, entity_id: uuid.UUID, field_name: str, new_values: list[str]
) -> None:
    """Remplace entièrement la liste d'un champ multi-valeur (ex: research_domains) :
    supersede les valeurs confirmées absentes de new_values, ajoute les nouvelles,
    puis écrase la colonne JSONB avec la liste finale — add_value seul ajoute mais
    ne retire jamais une valeur, nécessaire ici car l'édition remplace tout."""
    current_confirmed = (
        db.query(ResearcherFieldValue)
        .filter_by(entity_type=entity_type, entity_id=entity_id, field_name=field_name, validation_status="confirmed")
        .all()
    )
    for row in current_confirmed:
        if row.field_value not in new_values:
            row.validation_status = "superseded"
    db.flush()

    for value in new_values:
        add_value(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            field_name=field_name,
            field_value=value,
            source="user_added",
        )

    model = _get_target_model(entity_type)
    target = db.get(model, entity_id)
    if target is not None:
        setattr(target, field_name, list(new_values))
        
def clear_field(db: Session, *, entity_type: str, entity_id: uuid.UUID, field_name: str) -> None:
    """Efface entièrement un champ à valeur unique (ex: expertise_summary) :
    passe toutes ses lignes non-superseded à 'superseded' et remet la colonne
    matérialisée à None. Différent de edit_value (qui remplace par une
    nouvelle valeur) — ici on supprime sans rien remettre, pour permettre une
    régénération propre depuis zéro (bouton 'Supprimer', pas 'Modifier')."""
    rows = (
        db.query(ResearcherFieldValue)
        .filter(
            ResearcherFieldValue.entity_type == entity_type,
            ResearcherFieldValue.entity_id == entity_id,
            ResearcherFieldValue.field_name == field_name,
            ResearcherFieldValue.validation_status != "superseded",
        )
        .all()
    )
    for row in rows:
        row.validation_status = "superseded"

    model = _get_target_model(entity_type)
    target = db.get(model, entity_id)
    if target is not None:
        setattr(target, field_name, None)