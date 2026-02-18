"""
Data models for SageBridge

Contains all data structures used throughout the migration system.
"""

from .analysis import AnalysisReport, SourceCodeInfo, DependencyAnalysis, PatternAnalysis, RiskAssessment
from .artifacts import MigrationArtifacts, InfrastructureCode, TestingSuite, DocumentationPackage
from .validation import ValidationReport, CompatibilityCheck, SecurityValidation, CostAnalysis
from .deployment import DeploymentPlan, DeploymentResult, DeploymentStep

__all__ = [
    'AnalysisReport', 'SourceCodeInfo', 'DependencyAnalysis', 'PatternAnalysis', 'RiskAssessment',
    'MigrationArtifacts', 'InfrastructureCode', 'TestingSuite', 'DocumentationPackage',
    'ValidationReport', 'CompatibilityCheck', 'SecurityValidation', 'CostAnalysis',
    'DeploymentPlan', 'DeploymentResult', 'DeploymentStep'
]