"""Réexporte toutes les tables du domaine Entrepreneur — obligatoire pour qu'Alembic les détecte."""
from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_field_value import ProjectFieldValue
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.models.project_public_profile import ProjectPublicProfile

__all__ = [
    "Document",
    "DocumentVersion",
    "EntrepreneurProfile",
    "Project",
    "ProjectFieldValue",
    "ProjectLegalProfile",
    "ProjectPublicProfile",
]
