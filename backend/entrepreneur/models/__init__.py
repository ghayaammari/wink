"""Réexporte toutes les tables du domaine Entrepreneur — obligatoire pour qu'Alembic les détecte."""
from backend.entrepreneur.models.ai_act_data_profile import AiActDataProfile
from backend.entrepreneur.models.aipd_analysis import AipdAnalysis
from backend.entrepreneur.models.compliance_data_profile import ComplianceDataProfile
from backend.entrepreneur.models.document import Document
from backend.entrepreneur.models.document_generation_session import DocumentGenerationSession
from backend.entrepreneur.models.document_generation_variable_value import DocumentGenerationVariableValue
from backend.entrepreneur.models.document_version import DocumentVersion
from backend.entrepreneur.models.entrepreneur_profile import EntrepreneurProfile
from backend.entrepreneur.models.legal_announcement import LegalAnnouncement
from backend.entrepreneur.models.name_availability_check import NameAvailabilityCheck
from backend.entrepreneur.models.notification import Notification
from backend.entrepreneur.models.project import Project
from backend.entrepreneur.models.project_associate import ProjectAssociate
from backend.entrepreneur.models.project_copilot_conversation import ProjectCopilotConversation
from backend.entrepreneur.models.project_field_value import ProjectFieldValue
from backend.entrepreneur.models.project_fintech_gap_analysis import ProjectFintechGapAnalysis
from backend.entrepreneur.models.project_healthtech_gap_analysis import ProjectHealthtechGapAnalysis
from backend.entrepreneur.models.project_legal_profile import ProjectLegalProfile
from backend.entrepreneur.models.fintech_data_profile import FintechDataProfile
from backend.entrepreneur.models.healthtech_data_profile import HealthtechDataProfile
from backend.entrepreneur.models.project_ai_act_classification import ProjectAiActClassification
from backend.entrepreneur.models.project_ai_act_obligation import ProjectAiActObligation
from backend.entrepreneur.models.project_ai_act_obligation_history import ProjectAiActObligationHistory
from backend.entrepreneur.models.project_certification_estimation import ProjectCertificationEstimation
from backend.entrepreneur.models.project_certification_obligation import ProjectCertificationObligation
from backend.entrepreneur.models.project_fintech_classification import ProjectFintechClassification
from backend.entrepreneur.models.project_healthtech_classification import ProjectHealthtechClassification
from backend.entrepreneur.models.project_pitch_deck import ProjectPitchDeck
from backend.entrepreneur.models.project_pitch_profile import ProjectPitchProfile
from backend.entrepreneur.models.project_public_profile import ProjectPublicProfile
from backend.entrepreneur.models.project_sector_detection import ProjectSectorDetection
from backend.entrepreneur.models.project_rgpd_obligation import ProjectRgpdObligation
from backend.entrepreneur.models.project_rgpd_obligation_history import ProjectRgpdObligationHistory
from backend.entrepreneur.models.roadmap_node import RoadmapNode
from backend.entrepreneur.models.roadmap_node_dependency import RoadmapNodeDependency
from backend.entrepreneur.models.startup_roadmap_item import StartupRoadmapItem
from backend.entrepreneur.models.company_officer import CompanyOfficer

__all__ = [
    "AiActDataProfile",
    "AipdAnalysis",
    "ComplianceDataProfile",
    "Document",
    "DocumentGenerationSession",
    "DocumentGenerationVariableValue",
    "DocumentVersion",
    "EntrepreneurProfile",
    "LegalAnnouncement",
    "NameAvailabilityCheck",
    "Notification",
    "Project",
    "ProjectAssociate",
    "ProjectCopilotConversation",
    "FintechDataProfile",
    "HealthtechDataProfile",
    "ProjectFieldValue",
    "ProjectFintechGapAnalysis",
    "ProjectHealthtechGapAnalysis",
    "ProjectLegalProfile",
    "ProjectAiActClassification",
    "ProjectAiActObligation",
    "ProjectAiActObligationHistory",
    "ProjectCertificationEstimation",
    "ProjectCertificationObligation",
    "ProjectFintechClassification",
    "ProjectHealthtechClassification",
    "ProjectPitchDeck",
    "ProjectPitchProfile",
    "ProjectPublicProfile",
    "ProjectSectorDetection",
    "ProjectRgpdObligation",
    "ProjectRgpdObligationHistory",
    "RoadmapNode",
    "RoadmapNodeDependency",
    "StartupRoadmapItem",
    "CompanyOfficer",
]
