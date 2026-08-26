"""Schémas d'extraction pour le cas d'usage "import de document" de l'onboarding
entrepreneur (service 0.0.2/0.0.3). Un schéma par table cible — voir
`pipelines/default_pipeline.py` pour l'appel LLM séparé par schéma.

Champs exclus volontairement (non extractibles depuis un texte, ou gérés par le
système plutôt que par le contenu du document) :
- projects : id, entrepreneur_profile_id, imported_document_id, source_type,
  project_profile_completion, created_at, updated_at
- project_legal_profiles : id, project_id, is_registered (dérivé de project_type,
  voir la sous-étape de cohérence SIREN), verification_status, created_at, updated_at
- project_public_profiles : id, project_id, logo_url (image, pas du texte),
  funding_visibility, compliance_visibility, published_at, updated_at

Tous les champs sont optionnels : un document ne mentionne jamais tous les champs
d'une table, et `llm_service.extract_structured` a besoin que le champ non trouvé
reste `None` plutôt que de forcer le LLM à halluciner une valeur.

project_type et stage sont extraits ici mais ne doivent jamais être écrits
directement dans `projects` sans confirmation explicite de l'utilisateur — c'est
le rôle de la sous-étape de cohérence (Phase 5 du plan d'implémentation), pas de
ce module.
"""

from pydantic import BaseModel, Field


class ProjectExtractedFields(BaseModel):
    project_type: str | None = Field(
        default=None, description="'not_created' si idée/pas encore créée, 'created' si société déjà créée."
    )
    stage: str | None = Field(
        default=None, description="Un de : ideation, pre_seed, seed, serie_a."
    )
    description: str | None = Field(default=None, description="Description générale du projet.")
    nombre_cofondateurs: int | None = None
    intention_levee_fonds: bool | None = None
    localisation: str | None = Field(default=None, description="Ville ou région où le projet est basé.")
    sector: str | None = None
    subsectors: list[str] = Field(default_factory=list)
    customer_segments: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    value_proposition: str | None = None


class ProjectLegalProfileExtractedFields(BaseModel):
    legal_name: str | None = None
    legal_form: str | None = Field(default=None, description="Ex: SAS, SASU, SARL, EURL, SA, SNC.")
    registration_number: str | None = None
    siren: str | None = Field(default=None, description="9 chiffres.")
    siret: str | None = Field(default=None, description="14 chiffres.")
    vat_number: str | None = None
    naf_code: str | None = None
    registration_date: str | None = Field(default=None, description="Format ISO (YYYY-MM-DD) si trouvée.")
    registered_address: dict | None = None
    legal_representative: dict | None = None


class ProjectPublicProfileExtractedFields(BaseModel):
    public_name: str | None = None
    public_summary: str | None = None
    sector: str | None = None
    technologies: list[str] = Field(default_factory=list)
    website_url: str | None = None
