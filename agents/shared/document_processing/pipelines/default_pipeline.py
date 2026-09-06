"""Orchestre l'extraction d'un document entrepreneur : VLM (texte brut) → 3 appels
LLM séparés, un par table cible (projects, project_legal_profiles,
project_public_profiles).

Pourquoi 3 appels séparés plutôt qu'un seul schéma géant : chaque table a sa
propre responsabilité de validation en aval (project_field_values, un enregistrement
par champ) — un schéma unique grossirait à chaque nouvelle table cible sans
qu'aucune des tables n'ait besoin des champs des deux autres pour être validée.
"""

from agents.shared.document_processing.llm_extraction.llm_service import extract_structured
from agents.shared.document_processing.schemas.entrepreneur_project import (
    ProjectExtractedFields,
    ProjectLegalProfileExtractedFields,
    ProjectPublicProfileExtractedFields,
)
from agents.shared.document_processing.vlm_extraction.vlm_service import extract_text


def run(pdf_bytes: bytes) -> dict[str, dict]:
    """Retourne un dict {nom_de_table: {champ: valeur}}, valeur=None si le champ
    n'a pas été trouvé dans le document.
    """
    text = extract_text(pdf_bytes)

    return {
        "projects": extract_structured(text, ProjectExtractedFields, schema_key="projects").model_dump(),
        "project_legal_profiles": extract_structured(
            text, ProjectLegalProfileExtractedFields, schema_key="project_legal_profiles"
        ).model_dump(),
        "project_public_profiles": extract_structured(
            text, ProjectPublicProfileExtractedFields, schema_key="project_public_profiles"
        ).model_dump(),
    }
