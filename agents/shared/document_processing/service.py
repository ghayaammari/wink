"""Point d'entrée public du module d'extraction de document.

Dispatcher léger : aucune logique métier ici, seulement le routage vers le bon
pipeline selon `schema_name`. Un seul schéma pour l'instant
("entrepreneur_project") ; d'autres viendront avec chercheur/contract_agent sans
toucher aux pipelines existants — voir PIPELINE_MAP.

Usage (backend/entrepreneur/services/*) :
    from agents.shared.document_processing.service import extract_document
    resultat = extract_document(pdf_bytes, schema_name="entrepreneur_project")
"""

from agents.shared.document_processing.pipelines import default_pipeline

PIPELINE_MAP = {
    "entrepreneur_project": default_pipeline.run,
}


class DocumentProcessingError(Exception):
    """Schéma inconnu ou échec du pipeline sélectionné."""


def extract_document(pdf_bytes: bytes, *, schema_name: str) -> dict[str, dict]:
    pipeline = PIPELINE_MAP.get(schema_name)
    if pipeline is None:
        raise DocumentProcessingError(
            f"Schéma d'extraction inconnu : {schema_name!r}. Schémas disponibles : {list(PIPELINE_MAP)}."
        )
    return pipeline(pdf_bytes)
