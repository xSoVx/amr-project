"""
Medical Device Compliance Package
ISO 13485 & ISO 14971 Implementation for AMR Classification Engine
"""

from .risk_management_system import AMRRiskManagementSystem
from .clinical_evaluation import ClinicalEvaluationManager
from .software_validation import SoftwareValidationFramework
from .post_market_surveillance import PostMarketSurveillanceSystem
from .documentation_manager import MedicalDeviceDocumentationManager
from .regulatory_submission import RegulatorySubmissionManager
from .compliance_monitoring import ComplianceMonitoringSystem

__all__ = [
    "AMRRiskManagementSystem",
    "ClinicalEvaluationManager", 
    "SoftwareValidationFramework",
    "PostMarketSurveillanceSystem",
    "MedicalDeviceDocumentationManager",
    "RegulatorySubmissionManager",
    "ComplianceMonitoringSystem"
]

__version__ = "1.0.0"
__author__ = "Medical Device Development Team"
__email__ = "meddev@company.com"
__description__ = "Comprehensive medical device compliance implementation for AMR Classification Engine"