"""Schémas Pydantic pour la session interactive de génération de document
(service 1.1.13 — pacte de fondateurs). Voir document_generation_service.py
pour la logique métier que ces schémas encadrent.

RENOMMAGE (migration d9c4a6b1f3e8, 20/09/2026) : `scenario` -> `code_clause`,
`scenario_description` -> `description_clause`, `nom_section` -> `code_section`,
`type_contenu` -> `comportement_section` — voir la docstring des modèles
correspondants pour le pourquoi. Ces champs traversent tels quels jusqu'au
JSON de l'API (aucun `alias` Pydantic) : le frontend doit être mis à jour en
même temps (voir documentGenerationApi.ts).

AJOUT (migration b7e2f4a9c1d6, 20/09/2026) : `ClauseCandidateRead.sous_candidats`
et `SectionAnswerSubmit.sous_variante` — cas Article 3 uniquement (3 de ses 7
hypothèses ont un second niveau de choix imbriqué, voir docstring de
`ContractClauseLibrary`). `sous_candidats` est auto-référencé (une
sous-variante est elle-même un `ClauseCandidateRead`) pour ne pas dupliquer
le schéma — voir `model_rebuild()` en fin de fichier, requis par Pydantic
pour résoudre une référence différée sur soi-même.
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClauseCandidateRead(BaseModel):
    """Une clause candidate (mention obligatoire, clause optionnelle, ou une
    variante parmi un groupe) — assez de contenu pour l'afficher au frontend
    sans requête supplémentaire."""

    code_clause: str
    titre_clause: str
    description_clause: str
    texte_clause: str
    variables_requises: list[dict]
    # AJOUT 24/09/2026 — valeur déjà résolue des variables `auto_*` de cette
    # clause (ex. Préambule v2 : dénomination sociale, capital...), jamais
    # posées à l'utilisateur (voir `_resoudre_variables_auto` côté service).
    # Le frontend les affiche en lecture seule au lieu d'un champ éditable.
    # Absent (dict vide) pour une clause sans variable `auto_*`.
    valeurs_auto_resolues: dict[str, str] = Field(default_factory=dict)
    # Rempli seulement si cette clause a elle-même un second niveau de choix
    # (cas Article 3 uniquement, voir contract_clause_library.py) — la clause
    # RÉELLEMENT appliquée est alors la sous-variante choisie, pas celle-ci.
    sous_candidats: list["ClauseCandidateRead"] | None = None


class SectionStateRead(BaseModel):
    """État de la section en cours — GET /projects/{id}/document-generation/{document_type}."""

    session_id: UUID
    statut: Literal["en_cours", "complete"]
    code_section: str | None = None
    comportement_section: Literal["mention_obligatoire", "clause_optionnelle", "variante_obligatoire"] | None = None
    obligatoire: bool | None = None
    # Titre + explication à annoncer par le copilot AVANT la question (scénario
    # fonctionnel, Étape 2) — toujours résolus côté service, jamais None en pratique
    # pour une section_courante (soit portés par la clause, soit par
    # document_templates.titre_affiche/explication). Optionnels ici uniquement en
    # défense (squelette de données incomplet).
    titre_section: str | None = None
    explication_section: str | None = None
    # AJOUT 24/09/2026 (bouton "Précédent" + barre de progression du formulaire) :
    # nom_article — voir _nom_article_courant, heuristique par convention de
    # nommage, None si non résolu (dégradation silencieuse, pas une erreur).
    # position/total_sections_estime — voir _section_progress, total estimé
    # (peut baisser légèrement en cours de parcours, voir sa docstring).
    nom_article: str | None = None
    position: int | None = None
    total_sections_estime: int = 0
    # Rempli seulement par POST .../back (go_to_previous_section) : l'ancienne
    # réponse de la section restaurée, pour préremplir le formulaire plutôt que
    # de le rouvrir vide. Toujours None sur GET .../ (état courant normal).
    reponse_precedente: dict[str, Any] | None = None
    # AJOUT 24/09/2026 — seulement significatif quand statut='complete' et
    # section_courante=None : distingue "questionnaire fini, pas encore
    # finalisé" (False) de "déjà finalisé, revient sur cette session plus
    # tard" (True) — voir get_current_section_state. False par défaut
    # (état normal en_cours), pas None : évite un 3e état à gérer côté
    # frontend pour un champ qui n'est de toute façon lu que dans ce cas.
    document_deja_genere: bool = False
    # Rempli seulement pour mention_obligatoire/clause_optionnelle (une seule clause).
    clause: ClauseCandidateRead | None = None
    # Rempli seulement pour variante_obligatoire (plusieurs candidats au choix).
    candidats: list[ClauseCandidateRead] | None = None


class SectionAnswerSubmit(BaseModel):
    """POST /projects/{id}/document-generation/{document_type}/sections/{code_section}.

    Les champs sont mutuellement exclusifs selon le comportement_section de la
    section visée (voir document_generation_service.submit_section pour la
    validation précise — ce schéma n'impose que la forme, pas la cohérence
    métier) :
    - `clause_optionnelle` -> `inclus` (+ `valeurs` si inclus=true)
    - `variante_obligatoire` -> `variante` (+ `sous_variante` si la clause
      choisie a un second niveau — cas Article 3 uniquement, voir
      `ClauseCandidateRead.sous_candidats`) (+ `valeurs`), ou rien si la
      section est facultative et que l'utilisateur ne choisit aucune variante
    - `mention_obligatoire` -> seulement `valeurs`
    """

    inclus: bool | None = None
    variante: str | None = None
    sous_variante: str | None = None
    valeurs: dict[str, Any] = Field(default_factory=dict)


class DocumentGenerationSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    document_type: str
    statut: Literal["en_cours", "complete"]
    section_courante: str | None
    document_genere_id: UUID | None
    created_at: datetime
    updated_at: datetime


class GeneratedDocumentRead(BaseModel):
    """Réponse de la finalisation — POST .../finalize. Reflète `documents` +
    sa version courante, pas un schéma séparé pour éviter la duplication avec
    document_vault_schemas.py (mais délibérément un sous-ensemble minimal ici,
    pas un import croisé : cette route n'a besoin que de l'id et de l'URL)."""

    document_id: UUID
    document_type: str
    secure_url: str
    original_filename: str


# Requis par Pydantic pour résoudre la référence différée de ClauseCandidateRead
# sur elle-même (sous_candidats: list["ClauseCandidateRead"]) — sans ça, le
# schéma OpenAPI généré par FastAPI resterait cassé sur ce champ précis.
ClauseCandidateRead.model_rebuild()
