"""
Validation models for SageBridge

Data structures for validation results and reports.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

from .artifacts import MigrationArtifacts


class ValidationStatus(Enum):
    """Status of validation checks"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class CompatibilityCheck:
    """Individual compatibility check result"""
    check_name: str
    status: ValidationStatus
    message: str
    details: Dict[str, Any]
    severity: str  # low, medium, high, critical


@dataclass
class SecurityValidation:
    """Security validation results"""
    iam_policy_checks: List[CompatibilityCheck] = field(default_factory=list)
    encryption_checks: List[CompatibilityCheck] = field(default_factory=list)
    network_security_checks: List[CompatibilityCheck] = field(default_factory=list)
    access_control_checks: List[CompatibilityCheck] = field(default_factory=list)
    overall_security_score: float = 0.0
    
    @classmethod
    def create_placeholder(cls) -> 'SecurityValidation':
        """
        Create placeholder SecurityValidation with safe defaults.
        
        Returns:
            SecurityValidation object with empty lists and default values
        """
        return cls()


@dataclass
class CostAnalysis:
    """Cost analysis and optimization results"""
    estimated_monthly_cost: float
    cost_optimization_suggestions: List[str]
    instance_type_recommendations: Dict[str, str]
    storage_optimization: List[str]
    cost_alerts: List[str]


@dataclass
class PerformanceBenchmarks:
    """Performance benchmarking results"""
    training_performance: Dict[str, float]
    inference_performance: Dict[str, float]
    resource_utilization: Dict[str, float]
    bottlenecks: List[str]
    optimization_recommendations: List[str]


@dataclass
class ProductionReadinessScore:
    """Overall production readiness assessment"""
    overall_score: float
    security_score: float
    reliability_score: float
    performance_score: float
    maintainability_score: float
    readiness_level: str  # not_ready, partially_ready, production_ready


@dataclass
class ValidationReport:
    """Complete validation report"""
    compatibility_checks: List[CompatibilityCheck]
    security_validation: SecurityValidation
    cost_analysis: CostAnalysis
    performance_benchmarks: PerformanceBenchmarks
    production_readiness: ProductionReadinessScore
    validation_timestamp: str
    
    @classmethod
    def create_placeholder(cls, artifacts: MigrationArtifacts) -> 'ValidationReport':
        """Create placeholder validation report for testing"""
        import datetime
        
        return cls(
            compatibility_checks=[
                CompatibilityCheck(
                    check_name="SageMaker SDK v3 Compatibility",
                    status=ValidationStatus.PASSED,
                    message="All code uses SageMaker SDK v3 patterns",
                    details={"checked_files": 5, "issues_found": 0},
                    severity="high"
                ),
                CompatibilityCheck(
                    check_name="TorchScript Compatibility",
                    status=ValidationStatus.WARNING,
                    message="Some models may not be TorchScript compatible",
                    details={"models_checked": 2, "compatible": 1, "incompatible": 1},
                    severity="medium"
                )
            ],
            security_validation=SecurityValidation(
                iam_policy_checks=[
                    CompatibilityCheck(
                        check_name="Least Privilege IAM",
                        status=ValidationStatus.PASSED,
                        message="IAM policies follow least privilege principle",
                        details={"policies_checked": 3, "violations": 0},
                        severity="high"
                    )
                ],
                encryption_checks=[
                    CompatibilityCheck(
                        check_name="S3 Encryption",
                        status=ValidationStatus.PASSED,
                        message="All S3 buckets have encryption enabled",
                        details={"buckets_checked": 2, "encrypted": 2},
                        severity="high"
                    )
                ],
                network_security_checks=[],
                access_control_checks=[],
                overall_security_score=0.85
            ),
            cost_analysis=CostAnalysis(
                estimated_monthly_cost=250.0,
                cost_optimization_suggestions=[
                    "Use Spot instances for training",
                    "Enable S3 lifecycle policies"
                ],
                instance_type_recommendations={
                    "training": "ml.m5.large",
                    "inference": "ml.t3.medium"
                },
                storage_optimization=[
                    "Compress training data",
                    "Use S3 Intelligent Tiering"
                ],
                cost_alerts=[]
            ),
            performance_benchmarks=PerformanceBenchmarks(
                training_performance={"avg_epoch_time": 120.5, "throughput": 1000.0},
                inference_performance={"latency_p95": 50.0, "throughput": 500.0},
                resource_utilization={"cpu": 0.75, "memory": 0.60, "gpu": 0.80},
                bottlenecks=["Data loading I/O"],
                optimization_recommendations=[
                    "Increase data loading workers",
                    "Use faster storage tier"
                ]
            ),
            production_readiness=ProductionReadinessScore(
                overall_score=0.82,
                security_score=0.85,
                reliability_score=0.80,
                performance_score=0.78,
                maintainability_score=0.85,
                readiness_level="production_ready"
            ),
            validation_timestamp=datetime.datetime.now().isoformat()
        )
    
    def has_errors(self) -> bool:
        """Check if validation has any errors"""
        # Check compatibility checks
        compatibility_errors = any(
            check.status == ValidationStatus.FAILED 
            for check in (self.compatibility_checks or [])
        )
        
        # Check security validation errors with null-safe access
        security_errors = False
        if self.security_validation:
            # Check all security validation check lists
            security_check_lists = [
                getattr(self.security_validation, 'iam_policy_checks', []) or [],
                getattr(self.security_validation, 'encryption_checks', []) or [],
                getattr(self.security_validation, 'network_security_checks', []) or [],
                getattr(self.security_validation, 'access_control_checks', []) or []
            ]
            
            for check_list in security_check_lists:
                if any(check.status == ValidationStatus.FAILED for check in check_list):
                    security_errors = True
                    break
        
        return compatibility_errors or security_errors
    
    def has_warnings(self) -> bool:
        """Check if validation has any warnings"""
        # Check compatibility warnings
        compatibility_warnings = any(
            check.status == ValidationStatus.WARNING 
            for check in (self.compatibility_checks or [])
        )
        
        # Check security validation warnings with null-safe access
        security_warnings = False
        if self.security_validation:
            # Check all security validation check lists
            security_check_lists = [
                getattr(self.security_validation, 'iam_policy_checks', []) or [],
                getattr(self.security_validation, 'encryption_checks', []) or [],
                getattr(self.security_validation, 'network_security_checks', []) or [],
                getattr(self.security_validation, 'access_control_checks', []) or []
            ]
            
            for check_list in security_check_lists:
                if any(check.status == ValidationStatus.WARNING for check in check_list):
                    security_warnings = True
                    break
        
        return compatibility_warnings or security_warnings
    
    def get_errors(self) -> List[str]:
        """Get list of error messages"""
        errors = []
        
        # Get compatibility check errors
        for check in (self.compatibility_checks or []):
            if check.status == ValidationStatus.FAILED:
                errors.append(f"{check.check_name}: {check.message}")
        
        # Get security validation errors with null-safe access
        if self.security_validation:
            # Define security check categories and their lists
            security_categories = [
                ('IAM Policy', getattr(self.security_validation, 'iam_policy_checks', []) or []),
                ('Encryption', getattr(self.security_validation, 'encryption_checks', []) or []),
                ('Network Security', getattr(self.security_validation, 'network_security_checks', []) or []),
                ('Access Control', getattr(self.security_validation, 'access_control_checks', []) or [])
            ]
            
            for category_name, check_list in security_categories:
                for check in check_list:
                    if check.status == ValidationStatus.FAILED:
                        errors.append(f"Security ({category_name}) - {check.check_name}: {check.message}")
        
        return errors
    
    def get_warnings(self) -> List[str]:
        """Get list of warning messages"""
        warnings = []
        
        # Get compatibility check warnings
        for check in (self.compatibility_checks or []):
            if check.status == ValidationStatus.WARNING:
                warnings.append(f"{check.check_name}: {check.message}")
        
        # Get security validation warnings with null-safe access
        if self.security_validation:
            # Define security check categories and their lists
            security_categories = [
                ('IAM Policy', getattr(self.security_validation, 'iam_policy_checks', []) or []),
                ('Encryption', getattr(self.security_validation, 'encryption_checks', []) or []),
                ('Network Security', getattr(self.security_validation, 'network_security_checks', []) or []),
                ('Access Control', getattr(self.security_validation, 'access_control_checks', []) or [])
            ]
            
            for category_name, check_list in security_categories:
                for check in check_list:
                    if check.status == ValidationStatus.WARNING:
                        warnings.append(f"Security ({category_name}) - {check.check_name}: {check.message}")
        
        return warnings
    
    def save_to_file(self, file_path: Path) -> None:
        """Save validation report to JSON file"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(asdict(self), f, indent=2, default=str)
    
    @classmethod
    def load_from_file(cls, file_path: Path) -> 'ValidationReport':
        """Load validation report from JSON file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of validation results"""
        return {
            "overall_score": self.production_readiness.overall_score,
            "readiness_level": self.production_readiness.readiness_level,
            "total_checks": len(self.compatibility_checks),
            "passed_checks": len([c for c in self.compatibility_checks if c.status == ValidationStatus.PASSED]),
            "failed_checks": len([c for c in self.compatibility_checks if c.status == ValidationStatus.FAILED]),
            "warning_checks": len([c for c in self.compatibility_checks if c.status == ValidationStatus.WARNING]),
            "security_score": self.security_validation.overall_security_score,
            "estimated_monthly_cost": self.cost_analysis.estimated_monthly_cost
        }