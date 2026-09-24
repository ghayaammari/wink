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
    # AJOUT (25/09/2026, service 1.1.4 statuts) — BUG CORRIGÉ : ce champ est
    # calculé et placé dans le payload par `_clause_payload` depuis le tout
    # début de `_selections_requises` (23/09/2026), mais absent de CE schéma
    # jusqu'ici. Un `response_model` Pydantic ignore silencieusement toute
    # clé qui n'est pas déclarée dans le modèle : le champ était donc calculé
    # côté service puis jeté à la sérialisation, sans jamais atteindre le
    # frontend, sans erreur ni log. Découvert en préparant le frontend
    # statuts (le dropdown `auto_identite_associe` et les champs par-associé
    # `texte_par_associe`/`nombre_par_associe` en dépendent entièrement) —
    # même mécanisme pour le pacte (Article 8 `fondateur_avantage`), donc
    # déjà silencieusement cassé là aussi avant ce correctif.
    # Forme : {nom_variable: [{"id": <uuid associé>, "libelle": <identité affichable>}]}
    # — voir la docstring de `_selections_requises` côté service pour les 2
    # cas couverts (choix réel vs. saisie répétée par associé).
    selections_requises: dict[str, list[dict[str, str]]] = Field(default_factory=dict)
    # Rempli seulement si cette clause a elle-même un second niveau de choix
    # (cas Article 3 uniquement, voir contract_clause_library.py) — la clause
    # RÉELLEMENT appliquée est alors la sous-variante choisie, pas celle-ci.
    sous_candidats: list["ClauseCandidateRead"] | None = None


class FacultatifRead(BaseModel):
    """Un article facultatif proposé sur l'écran de choix (audit #19, statuts)."""

    code: str
    titre: str
    articles: list[str]
    explication: str
    # Pré-rempli avec le choix précédent si l'utilisateur revient sur l'écran.
    choisi: bool = False


class FacultatifsChoixSubmit(BaseModel):
    """POST .../facultatifs — codes des articles facultatifs cochés (liste vide
    = aucun). Les codes inconnus sont refusés par le service."""

    codes_choisis: list[str] = Field(default_factory=list)


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
    # Correction d'une section lancée depuis la vérification finale (statuts,
    # 24/09/2026) : bandeau « Revenir à la vérification », « Section
    # précédente » masqué.
    correction_en_cours: bool = False
    # AJOUT 24/09/2026 (audit #19, statuts) — écran de choix des facultatifs :
    # `choix_facultatifs_requis` vrai = pause avant l'Art. 8, `facultatifs` donne
    # la liste à cocher (code_section vaut alors "__choix_facultatifs__").
    choix_facultatifs_requis: bool = False
    facultatifs: list[FacultatifRead] | None = None
    # Vrai si la section courante appartient à un article facultatif coché :
    # le frontend ne redemande pas "l'inclure ?" et propose "Ne plus inclure".
    article_facultatif_choisi: bool = False
    # Vrai seulement pour la section de base de cet article : incluse d'office,
    # pas de question oui/non (ses options internes restent posées).
    section_de_base_facultatif: bool = False
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
    # Règles de validité (statuts, 24/09/2026) : `True` quand l'utilisateur a
    # vu les AVERTISSEMENTS (jamais les blocages) et choisit de continuer.
    confirmer_avertissements: bool = False


# RETIRÉ (27/09/2026, service 1.1.15) : ClauseExplanationRequest/Read et
# SectionAnsweredRead — l'explication de clause (à la demande ou
# automatique) est désormais portée par pacte_fondateur_copilot_schemas.py,
# voir document_generation_router.py pour la décision de consolidation.


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


class PrevalidationProblemeRead(BaseModel):
    """Un problème bloquant de la pré-validation (statuts, 24/09/2026).
    `page` : où le corriger (`informations_legales`, `equipe_capital`,
    `dirigeants`) -- le frontend en fait un lien direct."""

    code: str
    message: str
    page: str


class ProblemeValidationRead(BaseModel):
    """Un problème de la vérification finale (agents/document_generation_validation).
    `cible_type` = "section" (rouvrir `cible`) ou "page" (page du projet), ou None."""

    code: str
    message_court: str
    message: str
    gravite: Literal["bloquant", "avertissement"]
    cible_type: Literal["section", "page"] | None = None
    cible: str | None = None
    cible_libelle: str | None = None
    base_legale: str | None = None
    reformulation_proposee: str | None = None
    champ: str | None = None
    valeur_actuelle: str | None = None
    correction_proposee: str | None = None
    # {"variable", "valeur"} : correction certaine, bouton « Appliquer ».
    valeur_a_appliquer: dict[str, str] | None = None


class CorrectionAppliqueeSubmit(BaseModel):
    """POST …/validation-finale/appliquer : enregistre la valeur proposée par
    la vérification finale dans une section déjà répondue."""

    code_section: str
    variable: str
    valeur: str


class EtapeValidationRead(BaseModel):
    tool: str
    libelle: str
    statut: Literal["ok", "problemes", "erreur"]
    duree_ms: int
    nb_problemes: int


class ValidationFinaleRead(BaseModel):
    """GET …/document-generation/{type}/validation-finale. `pret` = aucun
    problème bloquant (des avertissements seuls n'empêchent pas de générer)."""

    pret: bool
    etapes: list[EtapeValidationRead]
    problemes: list[ProblemeValidationRead]


class PrevalidationRead(BaseModel):
    """GET …/document-generation/{type}/prevalidation. `pret=False` : la
    rédaction ne peut pas commencer tant que `problemes` n'est pas vide."""

    pret: bool
    problemes: list[PrevalidationProblemeRead]
