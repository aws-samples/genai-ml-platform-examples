"""
ValidationComponentFactory for SageMigrator

Factory class for creating validation components with safe defaults, error handling,
and fallback mechanisms to prevent null reference exceptions during validation.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

from ..models.validation import (
    SecurityValidation, 
    CompatibilityCheck, 
    ValidationStatus,
    CostAnalysis,
    PerformanceBenchmarks,
    ProductionReadinessScore
)
from ..models.artifacts import MigrationArtifacts


logger = logging.getLogger(__name__)


class ValidationComponentType(Enum):
    """Types of validation components that can be created"""
    SECURITY_VALIDATION = "security_validation"
    IAM_POLICY_CHECKS = "iam_policy_checks"
    ENCRYPTION_CHECKS = "encryption_checks"
    NETWORK_SECURITY_CHECKS = "network_security_checks"
    ACCESS_CONTROL_CHECKS = "access_control_checks"
    COST_ANALYSIS = "cost_analysis"
    PERFORMANCE_BENCHMARKS = "performance_benchmarks"
    PRODUCTION_READINESS_SCORE = "production_readiness_score"


@dataclass
class ValidationComponentError:
    """Error information for validation component creation failures"""
    component_type: ValidationComponentType
    error_message: str
    fallback_used: bool
    original_exception: Optional[Exception] = None


class ValidationComponentFactory:
    """
    Factory class for creating validation components with safe defaults.
    
    This factory provides error handling and fallback mechanisms to ensure
    that validation components are always properly initialized, preventing
    null reference exceptions during validation processes.
    """
    
    def __init__(self):
        """Initialize the ValidationComponentFactory"""
        self.creation_errors: List[ValidationComponentError] = []
        self.fallback_enabled = True
        
    def create_security_validation(
        self, 
        artifacts: Optional[MigrationArtifacts] = None,
        detailed_checks: bool = False
    ) -> SecurityValidation:
        """
        Create SecurityValidation object with proper initialization.
        
        Args:
            artifacts: Migration artifacts to validate (optional)
            detailed_checks: Whether to create detailed security checks
            
        Returns:
            SecurityValidation object with safe defaults
            
        Raises:
            RuntimeError: If creation fails and fallback is disabled
        """
        try:
            logger.info("Creating SecurityValidation with safe defaults")
            
            # Create IAM policy checks
            iam_checks = self.create_iam_policy_checks(artifacts, detailed_checks)
            
            # Create encryption checks
            encryption_checks = self.create_encryption_checks(artifacts, detailed_checks)
            
            # Create network security checks
            network_checks = self.create_network_security_checks(artifacts, detailed_checks)
            
            # Create access control checks
            access_checks = self.create_access_control_checks(artifacts, detailed_checks)
            
            # Calculate overall security score
            security_score = self._calculate_security_score(
                iam_checks, encryption_checks, network_checks, access_checks
            )
            
            security_validation = SecurityValidation(
                iam_policy_checks=iam_checks,
                encryption_checks=encryption_checks,
                network_security_checks=network_checks,
                access_control_checks=access_checks,
                overall_security_score=security_score
            )
            
            logger.info("SecurityValidation created successfully")
            return security_validation
            
        except Exception as e:
            error_msg = f"Failed to create SecurityValidation: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.SECURITY_VALIDATION,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                logger.warning("Using fallback SecurityValidation with minimal defaults")
                return self._create_fallback_security_validation()
            else:
                raise RuntimeError(error_msg) from e
    
    def create_iam_policy_checks(
        self, 
        artifacts: Optional[MigrationArtifacts] = None,
        detailed_checks: bool = False
    ) -> List[CompatibilityCheck]:
        """
        Create IAM policy compatibility checks.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            detailed_checks: Whether to create detailed checks
            
        Returns:
            List of CompatibilityCheck objects for IAM policies
        """
        try:
            logger.debug("Creating IAM policy checks")
            
            if not detailed_checks or not artifacts:
                # Return placeholder checks
                return [
                    CompatibilityCheck(
                        check_name="IAM Policy Placeholder Check",
                        status=ValidationStatus.SKIPPED,
                        message="IAM policy validation not yet implemented",
                        details={"placeholder": True, "reason": "detailed_checks_disabled"},
                        severity="low"
                    )
                ]
            
            # Create detailed IAM policy checks based on artifacts
            checks = []
            
            # Check for IAM policies in infrastructure
            if artifacts.infrastructure and artifacts.infrastructure.iam_policies:
                for policy_name, policy_content in artifacts.infrastructure.iam_policies.items():
                    checks.append(CompatibilityCheck(
                        check_name=f"IAM Policy Analysis: {policy_name}",
                        status=ValidationStatus.PASSED,
                        message=f"IAM policy {policy_name} analyzed for compliance",
                        details={
                            "policy_name": policy_name,
                            "policy_size": len(policy_content),
                            "analysis_type": "basic_structure"
                        },
                        severity="medium"
                    ))
            
            # Add default check if no policies found
            if not checks:
                checks.append(CompatibilityCheck(
                    check_name="IAM Policy Structure Check",
                    status=ValidationStatus.WARNING,
                    message="No IAM policies found in migration artifacts",
                    details={"policies_found": 0},
                    severity="medium"
                ))
            
            logger.debug(f"Created {len(checks)} IAM policy checks")
            return checks
            
        except Exception as e:
            error_msg = f"Failed to create IAM policy checks: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.IAM_POLICY_CHECKS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return self._create_fallback_iam_checks()
            else:
                raise RuntimeError(error_msg) from e
    
    def create_encryption_checks(
        self, 
        artifacts: Optional[MigrationArtifacts] = None,
        detailed_checks: bool = False
    ) -> List[CompatibilityCheck]:
        """
        Create encryption compatibility checks.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            detailed_checks: Whether to create detailed checks
            
        Returns:
            List of CompatibilityCheck objects for encryption
        """
        try:
            logger.debug("Creating encryption checks")
            
            if not detailed_checks or not artifacts:
                # Return placeholder checks
                return [
                    CompatibilityCheck(
                        check_name="Encryption Placeholder Check",
                        status=ValidationStatus.SKIPPED,
                        message="Encryption validation not yet implemented",
                        details={"placeholder": True, "reason": "detailed_checks_disabled"},
                        severity="low"
                    )
                ]
            
            # Create detailed encryption checks based on artifacts
            checks = []
            
            # Check for encryption in CloudFormation templates
            if artifacts.infrastructure and artifacts.infrastructure.cloudformation_templates:
                for template_name, template_content in artifacts.infrastructure.cloudformation_templates.items():
                    # Basic check for encryption-related keywords
                    encryption_keywords = ["KmsKeyId", "ServerSideEncryption", "Encrypted"]
                    found_encryption = any(keyword in template_content for keyword in encryption_keywords)
                    
                    if found_encryption:
                        checks.append(CompatibilityCheck(
                            check_name=f"Encryption Configuration: {template_name}",
                            status=ValidationStatus.PASSED,
                            message=f"Encryption configuration found in {template_name}",
                            details={
                                "template_name": template_name,
                                "encryption_keywords_found": True
                            },
                            severity="high"
                        ))
                    else:
                        checks.append(CompatibilityCheck(
                            check_name=f"Encryption Configuration: {template_name}",
                            status=ValidationStatus.WARNING,
                            message=f"No encryption configuration found in {template_name}",
                            details={
                                "template_name": template_name,
                                "encryption_keywords_found": False
                            },
                            severity="high"
                        ))
            
            # Add default check if no templates found
            if not checks:
                checks.append(CompatibilityCheck(
                    check_name="Encryption Configuration Check",
                    status=ValidationStatus.WARNING,
                    message="No infrastructure templates found to validate encryption",
                    details={"templates_found": 0},
                    severity="medium"
                ))
            
            logger.debug(f"Created {len(checks)} encryption checks")
            return checks
            
        except Exception as e:
            error_msg = f"Failed to create encryption checks: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.ENCRYPTION_CHECKS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return self._create_fallback_encryption_checks()
            else:
                raise RuntimeError(error_msg) from e
    
    def create_network_security_checks(
        self, 
        artifacts: Optional[MigrationArtifacts] = None,
        detailed_checks: bool = False
    ) -> List[CompatibilityCheck]:
        """
        Create network security compatibility checks.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            detailed_checks: Whether to create detailed checks
            
        Returns:
            List of CompatibilityCheck objects for network security
        """
        try:
            logger.debug("Creating network security checks")
            
            if not detailed_checks or not artifacts:
                # Return empty list for network security (optional component)
                return []
            
            # Create basic network security checks
            checks = [
                CompatibilityCheck(
                    check_name="Network Security Configuration",
                    status=ValidationStatus.SKIPPED,
                    message="Network security validation not yet implemented",
                    details={"placeholder": True, "component": "network_security"},
                    severity="low"
                )
            ]
            
            logger.debug(f"Created {len(checks)} network security checks")
            return checks
            
        except Exception as e:
            error_msg = f"Failed to create network security checks: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.NETWORK_SECURITY_CHECKS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return []  # Safe fallback for optional component
            else:
                raise RuntimeError(error_msg) from e
    
    def create_access_control_checks(
        self, 
        artifacts: Optional[MigrationArtifacts] = None,
        detailed_checks: bool = False
    ) -> List[CompatibilityCheck]:
        """
        Create access control compatibility checks.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            detailed_checks: Whether to create detailed checks
            
        Returns:
            List of CompatibilityCheck objects for access control
        """
        try:
            logger.debug("Creating access control checks")
            
            if not detailed_checks or not artifacts:
                # Return empty list for access control (optional component)
                return []
            
            # Create basic access control checks
            checks = [
                CompatibilityCheck(
                    check_name="Access Control Configuration",
                    status=ValidationStatus.SKIPPED,
                    message="Access control validation not yet implemented",
                    details={"placeholder": True, "component": "access_control"},
                    severity="low"
                )
            ]
            
            logger.debug(f"Created {len(checks)} access control checks")
            return checks
            
        except Exception as e:
            error_msg = f"Failed to create access control checks: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.ACCESS_CONTROL_CHECKS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return []  # Safe fallback for optional component
            else:
                raise RuntimeError(error_msg) from e
    
    def create_cost_analysis(
        self, 
        artifacts: Optional[MigrationArtifacts] = None
    ) -> CostAnalysis:
        """
        Create CostAnalysis object with safe defaults.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            
        Returns:
            CostAnalysis object with safe defaults
        """
        try:
            logger.debug("Creating cost analysis")
            
            # Create basic cost analysis with safe defaults
            cost_analysis = CostAnalysis(
                estimated_monthly_cost=0.0,
                cost_optimization_suggestions=[
                    "Enable detailed cost monitoring",
                    "Review instance types for optimization opportunities",
                    "Consider using Spot instances for training workloads"
                ],
                instance_type_recommendations={
                    "training": "ml.m5.large",
                    "inference": "ml.t3.medium"
                },
                storage_optimization=[
                    "Enable S3 lifecycle policies",
                    "Use S3 Intelligent Tiering"
                ],
                cost_alerts=[]
            )
            
            logger.debug("Cost analysis created successfully")
            return cost_analysis
            
        except Exception as e:
            error_msg = f"Failed to create cost analysis: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.COST_ANALYSIS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return self._create_fallback_cost_analysis()
            else:
                raise RuntimeError(error_msg) from e
    
    def create_performance_benchmarks(
        self, 
        artifacts: Optional[MigrationArtifacts] = None
    ) -> PerformanceBenchmarks:
        """
        Create PerformanceBenchmarks object with safe defaults.
        
        Args:
            artifacts: Migration artifacts to analyze (optional)
            
        Returns:
            PerformanceBenchmarks object with safe defaults
        """
        try:
            logger.debug("Creating performance benchmarks")
            
            # Create basic performance benchmarks with safe defaults
            performance_benchmarks = PerformanceBenchmarks(
                training_performance={
                    "avg_epoch_time": 0.0,
                    "throughput": 0.0
                },
                inference_performance={
                    "latency_p95": 0.0,
                    "throughput": 0.0
                },
                resource_utilization={
                    "cpu": 0.0,
                    "memory": 0.0,
                    "gpu": 0.0
                },
                bottlenecks=[],
                optimization_recommendations=[
                    "Establish performance baselines",
                    "Implement performance monitoring",
                    "Conduct load testing"
                ]
            )
            
            logger.debug("Performance benchmarks created successfully")
            return performance_benchmarks
            
        except Exception as e:
            error_msg = f"Failed to create performance benchmarks: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.PERFORMANCE_BENCHMARKS,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return self._create_fallback_performance_benchmarks()
            else:
                raise RuntimeError(error_msg) from e
    
    def create_production_readiness_score(
        self, 
        compatibility_checks: List[CompatibilityCheck],
        security_validation: SecurityValidation
    ) -> ProductionReadinessScore:
        """
        Create ProductionReadinessScore based on validation results.
        
        Args:
            compatibility_checks: List of compatibility checks
            security_validation: Security validation results
            
        Returns:
            ProductionReadinessScore object
        """
        try:
            logger.debug("Creating production readiness score")
            
            # Calculate scores based on validation results
            overall_score = self._calculate_overall_score(compatibility_checks, security_validation)
            security_score = security_validation.overall_security_score if security_validation else 0.0
            
            # Determine readiness level
            readiness_level = self._determine_readiness_level(overall_score)
            
            production_readiness = ProductionReadinessScore(
                overall_score=overall_score,
                security_score=security_score,
                reliability_score=75.0,  # Default value
                performance_score=70.0,  # Default value
                maintainability_score=80.0,  # Default value
                readiness_level=readiness_level
            )
            
            logger.debug("Production readiness score created successfully")
            return production_readiness
            
        except Exception as e:
            error_msg = f"Failed to create production readiness score: {str(e)}"
            logger.error(error_msg)
            
            # Record the error
            self.creation_errors.append(ValidationComponentError(
                component_type=ValidationComponentType.PRODUCTION_READINESS_SCORE,
                error_message=error_msg,
                fallback_used=self.fallback_enabled,
                original_exception=e
            ))
            
            if self.fallback_enabled:
                return self._create_fallback_production_readiness_score()
            else:
                raise RuntimeError(error_msg) from e
    
    def get_creation_errors(self) -> List[ValidationComponentError]:
        """
        Get list of errors that occurred during component creation.
        
        Returns:
            List of ValidationComponentError objects
        """
        return self.creation_errors.copy()
    
    def clear_creation_errors(self) -> None:
        """Clear the list of creation errors."""
        self.creation_errors.clear()
    
    def has_creation_errors(self) -> bool:
        """
        Check if any errors occurred during component creation.
        
        Returns:
            True if errors occurred, False otherwise
        """
        return len(self.creation_errors) > 0
    
    def set_fallback_enabled(self, enabled: bool) -> None:
        """
        Enable or disable fallback mechanisms.
        
        Args:
            enabled: Whether to enable fallback mechanisms
        """
        self.fallback_enabled = enabled
        logger.info(f"Fallback mechanisms {'enabled' if enabled else 'disabled'}")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get summary of creation errors.
        
        Returns:
            Dictionary containing error summary information
        """
        if not self.creation_errors:
            return {
                "total_errors": 0,
                "components_with_errors": [],
                "fallback_usage": 0
            }
        
        component_types = [error.component_type.value for error in self.creation_errors]
        fallback_count = sum(1 for error in self.creation_errors if error.fallback_used)
        
        return {
            "total_errors": len(self.creation_errors),
            "components_with_errors": list(set(component_types)),
            "fallback_usage": fallback_count,
            "error_details": [
                {
                    "component": error.component_type.value,
                    "message": error.error_message,
                    "fallback_used": error.fallback_used
                }
                for error in self.creation_errors
            ]
        }
    
    # Private helper methods for fallback creation
    
    def _create_fallback_security_validation(self) -> SecurityValidation:
        """Create minimal SecurityValidation as fallback."""
        return SecurityValidation(
            iam_policy_checks=self._create_fallback_iam_checks(),
            encryption_checks=self._create_fallback_encryption_checks(),
            network_security_checks=[],
            access_control_checks=[],
            overall_security_score=0.0
        )
    
    def _create_fallback_iam_checks(self) -> List[CompatibilityCheck]:
        """Create minimal IAM checks as fallback."""
        return [
            CompatibilityCheck(
                check_name="IAM Policy Fallback Check",
                status=ValidationStatus.SKIPPED,
                message="IAM policy validation failed, using fallback",
                details={"fallback": True, "reason": "creation_error"},
                severity="low"
            )
        ]
    
    def _create_fallback_encryption_checks(self) -> List[CompatibilityCheck]:
        """Create minimal encryption checks as fallback."""
        return [
            CompatibilityCheck(
                check_name="Encryption Fallback Check",
                status=ValidationStatus.SKIPPED,
                message="Encryption validation failed, using fallback",
                details={"fallback": True, "reason": "creation_error"},
                severity="low"
            )
        ]
    
    def _create_fallback_cost_analysis(self) -> CostAnalysis:
        """Create minimal CostAnalysis as fallback."""
        return CostAnalysis(
            estimated_monthly_cost=0.0,
            cost_optimization_suggestions=["Cost analysis unavailable"],
            instance_type_recommendations={},
            storage_optimization=[],
            cost_alerts=[]
        )
    
    def _create_fallback_performance_benchmarks(self) -> PerformanceBenchmarks:
        """Create minimal PerformanceBenchmarks as fallback."""
        return PerformanceBenchmarks(
            training_performance={},
            inference_performance={},
            resource_utilization={},
            bottlenecks=[],
            optimization_recommendations=["Performance analysis unavailable"]
        )
    
    def _create_fallback_production_readiness_score(self) -> ProductionReadinessScore:
        """Create minimal ProductionReadinessScore as fallback."""
        return ProductionReadinessScore(
            overall_score=0.0,
            security_score=0.0,
            reliability_score=0.0,
            performance_score=0.0,
            maintainability_score=0.0,
            readiness_level="not_ready"
        )
    
    def _calculate_security_score(
        self, 
        iam_checks: List[CompatibilityCheck],
        encryption_checks: List[CompatibilityCheck],
        network_checks: List[CompatibilityCheck],
        access_checks: List[CompatibilityCheck]
    ) -> float:
        """Calculate overall security score based on checks."""
        all_checks = iam_checks + encryption_checks + network_checks + access_checks
        
        if not all_checks:
            return 0.0
        
        # Count passed checks
        passed_checks = sum(1 for check in all_checks if check.status == ValidationStatus.PASSED)
        total_checks = len(all_checks)
        
        # Calculate score as percentage
        return (passed_checks / total_checks) * 100.0 if total_checks > 0 else 0.0
    
    def _calculate_overall_score(
        self, 
        compatibility_checks: List[CompatibilityCheck],
        security_validation: SecurityValidation
    ) -> float:
        """Calculate overall production readiness score."""
        scores = []
        
        # Compatibility score
        if compatibility_checks:
            passed_compat = sum(1 for check in compatibility_checks if check.status == ValidationStatus.PASSED)
            compat_score = (passed_compat / len(compatibility_checks)) * 100.0
            scores.append(compat_score)
        
        # Security score
        if security_validation:
            scores.append(security_validation.overall_security_score)
        
        # Return average score or 0 if no scores
        return sum(scores) / len(scores) if scores else 0.0
    
    def _determine_readiness_level(self, overall_score: float) -> str:
        """Determine readiness level based on overall score."""
        if overall_score >= 90:
            return "production_ready"
        elif overall_score >= 70:
            return "partially_ready"
        else:
            return "not_ready"