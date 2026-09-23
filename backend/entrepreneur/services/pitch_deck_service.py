"""Orchestration de la generation du pitch deck (service 6.6.2) : assemble

les donnees deja connues du projet (nom, pitch, logo, equipe) + le profil
pitch dedie (project_pitch_profiles), appelle l'agent, et met en cache le
resultat dans project_pitch_decks (une ligne par projet, ecrasee a chaque
regeneration -- voir le modele pour le raisonnement complet).

Ne fait AUCUN rendu de fichier ici : le PPTX est produit a la demande par
pitch_deck_renderer_service.py, jamais stocke (voir get_pptx_bytes).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from agents.pitch_deck_agent.deck_schema import BrandTheme, DeckContentModel
from agents.pitch_deck_agent.pitch_deck_content_service import (
    PitchGenerationInput,
    TeamMemberInput,
    generer_contenu_deck,
)
from backend.entrepreneur.models.project_pitch_deck import ProjectPitchDeck
from backend.entrepreneur.services.associate_service import list_associates
from backend.entrepreneur.services.pitch_deck_renderer_service import render_pptx
from backend.entrepreneur.services.pitch_profile_service import get_or_create_profile
from backend.entrepreneur.services.project_service import get_owned_project, get_public_profile
from backend.shared.models.user import User

# Couleur d'accent Wink par defaut (indigo-600) -- voir BrandTheme dans
# deck_schema.py : pas de champ couleur par projet pour l'instant.
_ACCENT_COLOR_DEFAUT = "#4F46E5"


class PitchDeckNotFoundError(Exception):
    """Aucun deck n'a encore ete genere pour ce projet -- traduit en 404 par pitch_router.py."""


def _construire_entree_agent(db: Session, user: User, project_id: UUID) -> PitchGenerationInput:
    project = get_owned_project(db, user, project_id)
    public_profile = get_public_profile(db, user, project_id)
    pitch_profile = get_or_create_profile(db, user, project_id)
    associates = list_associates(db, user, project_id)

    return PitchGenerationInput(
        startup_name=(public_profile.public_name if public_profile else None) or project.description or "Ma startup",
        one_liner=public_profile.public_summary if public_profile else None,
        secteur=public_profile.sector if public_profile else project.sector,
        probleme=pitch_profile.probleme,
        solution=pitch_profile.solution,
        marche=pitch_profile.marche,
        modele_economique=pitch_profile.modele_economique,
        concurrence=pitch_profile.concurrence,
        traction=pitch_profile.traction,
        financements=pitch_profile.financements,
        roadmap=pitch_profile.roadmap,
        demande_investissement=pitch_profile.demande_investissement,
        equipe=[
            TeamMemberInput(name=a.nom_complet, role=a.fonction_dirigeant or "Associe")
            for a in associates
        ],
    )


def generate_deck(db: Session, user: User, project_id: UUID) -> DeckContentModel:
    """Regeneration explicite (bouton "Generer/Regenerer", voir pitch_router.py).

    Leve PitchDeckAgentError si l'appel a l'agent echoue -- aucune ecriture
    en base dans ce cas (le dernier deck genere avec succes reste disponible)."""
    project = get_owned_project(db, user, project_id)
    public_profile = get_public_profile(db, user, project_id)
    entree = _construire_entree_agent(db, user, project_id)

    slides = generer_contenu_deck(entree)
    content = DeckContentModel(
        project_id=str(project.id),
        brand=BrandTheme(
            accent_color=_ACCENT_COLOR_DEFAUT,
            logo_url=public_profile.logo_url if public_profile else None,
        ),
        slides=slides,
    )

    deck = db.query(ProjectPitchDeck).filter(ProjectPitchDeck.project_id == project.id).first()
    if deck is None:
        deck = ProjectPitchDeck(project_id=project.id, content=content.model_dump(mode="json"))
        db.add(deck)
    else:
        deck.content = content.model_dump(mode="json")
    db.commit()

    return content


def get_latest_deck(db: Session, user: User, project_id: UUID) -> DeckContentModel:
    project = get_owned_project(db, user, project_id)
    deck = db.query(ProjectPitchDeck).filter(ProjectPitchDeck.project_id == project.id).first()
    if deck is None:
        raise PitchDeckNotFoundError("Aucun pitch deck n'a encore ete genere pour ce projet.")
    return DeckContentModel.model_validate(deck.content)


def get_pptx_bytes(db: Session, user: User, project_id: UUID) -> bytes:
    content = get_latest_deck(db, user, project_id)
    return render_pptx(content)
