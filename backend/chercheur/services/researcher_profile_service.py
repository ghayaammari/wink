"""Service métier — researcher_profiles.

Gère la lecture du profil, la finalisation de l'onboarding (étapes 3 à 5 du
parcours chercheur, envoyées en un seul appel POST /chercheur/onboarding) et
la modification post-onboarding (PATCH /chercheur/profile). Le déclenchement
de l'extraction HAL/OpenAlex n'est PAS automatique à la fin de l'onboarding
(décision actée — voir Wink_chercheur_I0_recap) : ce module se contente
d'enregistrer l'ORCID et de passer sync_status à 'queued', l'utilisateur
déclenche l'extraction lui-même via le bouton dédié (research_work_router,
qui appelle research_extraction_service.run_extraction directement)."""
import uuid

from sqlalchemy.orm import Session

from backend.chercheur.models.researcher_profile import ResearcherProfile
from backend.chercheur.schemas.researcher_profile_schemas import (
    ResearcherOnboardingRequest,
    ResearcherProfileUpdateRequest,
)
from backend.chercheur.services import researcher_field_value_service


class ResearcherProfileNotFoundError(Exception):
    pass


class MissingOrcidError(Exception):
    """ORCID requis quand extraction_preference != 'deposer'."""


def get_by_user_id(db: Session, user_id: uuid.UUID) -> ResearcherProfile:
    profile = db.query(ResearcherProfile).filter_by(user_id=user_id).first()
    if profile is None:
        # Ne devrait jamais arriver : auth_service crée le profil vide au signup.
        # Si ça arrive quand même, c'est un bug côté auth, pas côté chercheur.
        raise ResearcherProfileNotFoundError(f"Aucun researcher_profile pour user_id={user_id}")
    return profile


def get_profile_with_pending_fields(db: Session, user_id: uuid.UUID) -> ResearcherProfile:
    """Pour GET /chercheur/profile — même pattern que
    research_work_service.list_works_with_pending_fields : attache les
    field_values (affiliation, research_domains, expertise_summary,
    research_work_summary) en attribut Python avant sérialisation, pas une
    colonne réelle sur ResearcherProfile."""
    profile = get_by_user_id(db, user_id)
    profile.generated_field_values = researcher_field_value_service.list_all_for_entity(
        db, entity_type="researcher_profile", entity_id=profile.id
    )
    return profile


def complete_onboarding(
    db: Session,
    user_id: uuid.UUID,
    data: ResearcherOnboardingRequest,
) -> ResearcherProfile:
    """Ne déclenche plus l'extraction HAL/OpenAlex automatiquement (retiré le
    06/09/2026 — le code avait divergé de la décision actée dans le récap
    projet, causant un bug : réutiliser un ORCID déjà extrait sur un autre
    compte affichait immédiatement ses travaux sans jamais cliquer
    "Extraire"). sync_status passe à 'queued' pour signaler côté frontend
    qu'une extraction est possible/attendue, mais rien ne part tant que
    l'utilisateur n'a pas cliqué le bouton dédié (voir research_work_router)."""
    profile = get_by_user_id(db, user_id)

    needs_orcid = data.extraction_preference in ("extraire", "les_deux")
    if needs_orcid and not data.orcid_id:
        raise MissingOrcidError("orcid_id requis pour les préférences 'extraire' et 'les_deux'")

    if needs_orcid:
        profile.orcid_id = data.orcid_id
        profile.sync_status = "queued"

    # Affiliation saisie directement par l'utilisateur → confirmée et
    # matérialisée immédiatement, via le mécanisme polymorphe commun.
    researcher_field_value_service.add_value(
        db,
        entity_type="researcher_profile",
        entity_id=profile.id,
        field_name="affiliation",
        field_value=data.affiliation,
        source="user_added",
    )

    # research_domains n'est pas dans SINGLE_VALUE_FIELDS (voir
    # researcher_field_value_service) : chaque domaine devient sa propre ligne
    # confirmée, ajoutée à la liste existante plutôt que de la remplacer.
    for domain in data.research_domains:
        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=profile.id,
            field_name="research_domains",
            field_value=domain,
            source="user_added",
        )

    profile.profile_completion = "complet"
    db.commit()
    db.refresh(profile)

    return profile


def update_profile(
    db: Session, user_id: uuid.UUID, data: ResearcherProfileUpdateRequest
) -> ResearcherProfile:
    """PATCH /chercheur/profile — modification post-onboarding. Seuls les
    champs réellement envoyés par le frontend sont modifiés (model_fields_set
    distingue "champ absent du body" de "champ envoyé vide/null"), pour ne
    jamais écraser un champ que l'utilisateur n'a pas touché dans le
    formulaire d'édition.

    orcid_id est une colonne directe (pas de researcher_field_values, pas de
    mécanisme de validation) : changer l'ORCID ne redéclenche PAS
    automatiquement une nouvelle extraction HAL/OpenAlex — l'utilisateur
    reclique lui-même sur le bouton "Extraire" existant s'il le souhaite.
    Décision assumée pour rester simple (voir échange du 05/09/2026)."""
    profile = get_by_user_id(db, user_id)
    fields_set = data.model_fields_set

    if "orcid_id" in fields_set:
        profile.orcid_id = data.orcid_id

    if "affiliation" in fields_set and data.affiliation:
        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=profile.id,
            field_name="affiliation",
            field_value=data.affiliation,
            source="user_added",
        )

    if "research_domains" in fields_set and data.research_domains is not None:
        researcher_field_value_service.replace_multi_value(
            db,
            entity_type="researcher_profile",
            entity_id=profile.id,
            field_name="research_domains",
            new_values=data.research_domains,
        )

    if "expertise_summary" in fields_set and data.expertise_summary:
        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=profile.id,
            field_name="expertise_summary",
            field_value=data.expertise_summary,
            source="user_added",
        )

    if "research_work_summary" in fields_set and data.research_work_summary:
        researcher_field_value_service.add_value(
            db,
            entity_type="researcher_profile",
            entity_id=profile.id,
            field_name="research_work_summary",
            field_value=data.research_work_summary,
            source="user_added",
        )

    db.commit()
    db.refresh(profile)
    return profile