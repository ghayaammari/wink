"""Schémas Pydantic du dashboard de validation humaine (Phase 1.5, service
1.1.1, Étapes 1.5.2/1.5.3 du plan Notion) — même convention que
backend/chercheur/schemas/ : requête/réponse séparées des modèles SQLAlchemy
(legal_texts.py) et des routes (legal_texts_validation_router.py).
"""
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class LegalTextValidationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    article_numero: str | None
    forme_juridique_concernee: list[str]
    texte_brut: str
    chunking_suggere: str
    # Calculés à la volée par le routeur (Étape 1.5.1) — jamais des colonnes
    # DB : dérivés de texte_brut, affichés une fois pendant la validation,
    # pas besoin d'une donnée à resynchroniser à chaque modification.
    longueur_caracteres: int
    nb_alineas_detectes: int


class LegalTextValidationAction(BaseModel):
    # "valider" : statut_contenu -> valide_humain, chunking_suggere inchangé.
    # "corriger" : statut_contenu -> valide_humain, chunking_suggere inversé
    # (aucun <-> par_alinea) — seule correction permise par ce dashboard, voir
    # Étape 1.5.3 du plan Notion (pas d'édition libre du texte ici).
    action: Literal["valider", "corriger"]
